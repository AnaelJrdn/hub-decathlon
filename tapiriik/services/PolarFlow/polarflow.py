# Synchronization module for flow.polar.com
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.settings import WEB_ROOT, POLAR_CLIENT_SECRET, POLAR_CLIENT_ID, POLAR_RATE_LIMITS
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.api import APIException, UserException, UserExceptionType
from tapiriik.services.interchange import UploadedActivity, ActivityType, ActivityStatistic, ActivityStatisticUnit
from tapiriik.services.tcx import TCXIO

from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from urllib.parse import urlencode
from requests.auth import HTTPBasicAuth
from io import StringIO

import uuid
import gzip
import logging
import lxml
import pytz
import requests
import isodate

logger = logging.getLogger(__name__)

class PolarFlowService(ServiceBase):
    ID = "polarflow"
    DisplayName = "Polar Flow"
    DisplayAbbreviation = "PF"
    AuthenticationType = ServiceAuthenticationType.OAuth
    AuthenticationNoFrame = True # otherwise looks ugly in the small frame

    UserProfileURL = "https://flow.polar.com/training/profiles/{0}"
    UserActivityURL = "https://flow.polar.com/training/analysis/{1}"

    SupportsHR = SupportsCalories = SupportsCadence = SupportsTemp = SupportsPower = True

    ReceivesActivities = False # polar accesslink does not support polar data change.
    
    GlobalRateLimits = POLAR_RATE_LIMITS

    PartialSyncRequiresTrigger = True
    
    PartialSyncTriggerPollInterval = timedelta(minutes=1)

    # For mapping common->Polar Flow (text has no meaning due to upload unsupported)
    _activity_type_mappings = {
        ActivityType.Cycling: "Ride",
        ActivityType.MountainBiking: "Ride",
        ActivityType.Hiking: "Hike",
        ActivityType.Running: "Run",
        ActivityType.Walking: "Walk",
        ActivityType.Snowboarding: "Snowboard",
        ActivityType.Skating: "IceSkate",
        ActivityType.CrossCountrySkiing: "NordicSki",
        ActivityType.DownhillSkiing: "AlpineSki",
        ActivityType.Swimming: "Swim",
        ActivityType.Gym: "Workout",
        ActivityType.Rowing: "Rowing",
        ActivityType.RollerSkiing: "RollerSki",
        ActivityType.StrengthTraining: "WeightTraining",
        ActivityType.Climbing: "RockClimbing",
        ActivityType.Wheelchair: "Wheelchair",
        ActivityType.Other: "Other",
    }

    # Polar Flow -> common
    _reverse_activity_type_mappings = {
        "RUNNING": ActivityType.Running,
        "JOGGING": ActivityType.Running,
        "ROAD_RUNNING": ActivityType.Running,
        "TRACK_AND_FIELD_RUNNING": ActivityType.Running,
        "TRAIL_RUNNING": ActivityType.Running,
        "TREADMILL_RUNNING": ActivityType.Running,

        "CYCLING": ActivityType.Cycling,
        "ROAD_BIKING": ActivityType.Cycling,
        "INDOOR_CYCLING": ActivityType.Cycling,

        "MOUNTAIN_BIKING": ActivityType.MountainBiking,

        "WALKING": ActivityType.Walking,
        "HIKING": ActivityType.Hiking,
        "DOWNHILL_SKIING": ActivityType.DownhillSkiing,
        "CROSS-COUNTRY_SKIING": ActivityType.CrossCountrySkiing,
        "SNOWBOARDING": ActivityType.Snowboarding,
        "SKATING": ActivityType.Skating,

        "SWIMMING": ActivityType.Swimming,
        "OPEN_WATER_SWIMMING": ActivityType.Swimming,
        "POOL_SWIMMING": ActivityType.Swimming,

        "PARASPORTS_WHEELCHAIR": ActivityType.Wheelchair,
        "ROWING": ActivityType.Rowing,
        "INDOOR_ROWING": ActivityType.Rowing,
        "STRENGTH_TRAINING": ActivityType.StrengthTraining,

        "OTHER_INDOOR": ActivityType.Other,
        "OTHER_OUTDOOR": ActivityType.Other,

        "ROLLER_SKIING_CLASSIC": ActivityType.RollerSkiing,
        "ROLLER_SKIING_FREESTYLE": ActivityType.RollerSkiing,

        # not supported somehow
        #"": ActivityType.Elliptical,

        "FUNCTIONAL_TRAINING": ActivityType.Gym,
        "CORE": ActivityType.Gym,
        "GROUP_EXERCISE": ActivityType.Gym,
        "PILATES": ActivityType.Gym,
        "YOGA": ActivityType.Gym,

        "VERTICALSPORTS_WALLCLIMBING": ActivityType.Climbing,
    }

    SupportedActivities = list(_activity_type_mappings.keys())

    _api_endpoint = "https://www.polaraccesslink.com"

    def _register_user(self, access_token):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(access_token)
        }
        res = requests.post(self._api_endpoint + "/v3/users",
            json={"member-id": uuid.uuid4().hex},
            headers=headers)
        return res.status_code == 200

    def _delete_user(self, serviceRecord):
        res = requests.delete(self._api_endpoint + "/v3/users/{userid}".format(userid=serviceRecord.ExternalID),
            headers=self._api_headers(serviceRecord))

    def _create_transaction(self, serviceRecord):
        # Transaction contains max 50 items and last 10 minutes and after that it would be no acces to data within its scope
        # hope worker can download all data, otherwise still no issue - we will stop downloading  skipping exception
        # and fetch missed data later in scope of another transaction
        res = requests.post(self._api_endpoint +
            "/v3/users/{userid}/exercise-transactions".format(userid=serviceRecord.ExternalID),
            headers=self._api_headers(serviceRecord))
        # No new training data status_code=204
        if res.status_code == 401:
            #TODO why it could happen
            logger.debug("No authorization to create transaction")
            raise APIException("No authorization to create transaction", block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))
        
        transaction_uri = res.json()["resource-uri"] if res.status_code == 201 else None
        serviceRecord.ServiceData = {"Transaction-uri": transaction_uri}
        return transaction_uri

    def _commit_transaction(self, serviceRecord):
        if hasattr(serviceRecord, "ServiceData"):
            transaction_uri = serviceRecord.ServiceData["Transaction-uri"]
            if transaction_uri:
                res = requests.put(transaction_uri, headers=self._api_headers(serviceRecord))
        # TODO : should handle responce code?
        # 200	OK	Transaction has been committed and data deleted	None
        # 204	No Content	No content when there is no data available	None
        # 404	Not Found	No transaction was found with given transaction id	None

    def _api_headers(self, serviceRecord, headers={}):
        headers.update({"Authorization": "Bearer {}".format(serviceRecord.Authorization["OAuthToken"])})
        return headers

    def WebInit(self):
        params = {'response_type':'code',
                  'client_id': POLAR_CLIENT_ID,
                  'redirect_uri': WEB_ROOT + reverse("oauth_return", kwargs={"service": "polarflow"})}
        self.UserAuthorizationURL = "https://flow.polar.com/oauth2/authorization?" + urlencode(params)

    def RetrieveAuthorizationToken(self, req, level):
        code = req.GET.get("code")
        params = {"grant_type": "authorization_code",
                  "code": code,
                  "redirect_uri": WEB_ROOT + reverse("oauth_return", kwargs={"service": "polarflow"})}

        response = requests.post("https://polarremote.com/v2/oauth2/token", data=params, auth=HTTPBasicAuth(POLAR_CLIENT_ID, POLAR_CLIENT_SECRET))
        data = response.json()

        if response.status_code != 200:
            raise APIException(data["error"])

        authorizationData = {"OAuthToken": data["access_token"]}
        userId = data["x_user_id"]

        try:
            self._register_user(data["access_token"])
        except requests.exceptions.HTTPError as err:
            # Error 409 Conflict means that the user has already been registered for this client.
            # That error can be ignored
            if err.response.status_code != 409:
                raise APIException("Unable to link user", block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))

        return (userId, authorizationData)

    def RevokeAuthorization(self, serviceRecord):
        self._delete_user(serviceRecord)

    def SubscribeToPartialSyncTrigger(self, serviceRecord):
        # There is no per-user webhook subscription with Polar Flow.
        serviceRecord.SetPartialSyncTriggerSubscriptionState(True)

    def UnsubscribeFromPartialSyncTrigger(self, serviceRecord):
        # As above.
        serviceRecord.SetPartialSyncTriggerSubscriptionState(False)

    def PollPartialSyncTrigger(self, multiple_index):
        response = requests.get(self._api_endpoint + "/v3/notifications", auth=HTTPBasicAuth(POLAR_CLIENT_ID, POLAR_CLIENT_SECRET))

        to_sync_ids = []
        if response.status_code == 200:
            for item in response.json()["available-user-data"]:
                if item["data-type"] == "EXERCISE":
                    to_sync_ids.append(item["user-id"])

        return to_sync_ids

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        activities = []
        exclusions = []
        
        transaction_url = self._create_transaction(serviceRecord)
        if transaction_url:

            res = requests.get(transaction_url, headers=self._api_headers(serviceRecord))
            
            if res.status_code == 200: # otherwise no new data, skip
                for activity_url in res.json()["exercises"]:
                    data = requests.get(activity_url, headers=self._api_headers(serviceRecord))
                    if data.status_code == 200:
                        activity = self._create_activity(data.json())
                        activities.append(activity)
                    else:
                        # may be just deleted, who knows, skip
                        logger.debug("Cannot recieve training at url: {}".format(activity_url))

        return activities, exclusions

    def _create_activity(self, activity_data):
        activity = UploadedActivity()

        activity.GPS = not activity_data["has-route"]
        if "detailed-sport-info" in activity_data and activity_data["detailed-sport-info"] in self._reverse_activity_type_mappings:
            activity.Type = self._reverse_activity_type_mappings[activity_data["detailed-sport-info"]]
        else:
            activity.Type = ActivityType.Other

        activity.StartTime = pytz.utc.localize(isodate.parse_datetime(activity_data["start-time"]))
        activity.EndTime = activity.StartTime + isodate.parse_duration(activity_data["duration"])

        distance = activity_data["distance"] if "distance" in activity_data else None
        activity.Stats.Distance = ActivityStatistic(ActivityStatisticUnit.Meters, value=float(distance) if distance else None)
        hr_data = activity_data["heart-rate"] if "heart-rate" in activity_data else None
        avg_hr = hr_data["average"] if "average" in hr_data else None
        max_hr = hr_data["maximum"] if "maximum" in hr_data else None
        activity.Stats.HR.update(ActivityStatistic(ActivityStatisticUnit.BeatsPerMinute, avg=float(avg_hr) if avg_hr else None, max=float(max_hr) if max_hr else None))
        calories = activity_data["calories"] if "calories" in activity_data else None
        activity.Stats.Energy = ActivityStatistic(ActivityStatisticUnit.Kilocalories, value=int(calories) if calories else None)

        activity.ServiceData = {"ActivityID": activity_data["id"]}

        logger.debug("\tActivity s/t {}: {}".format(activity.StartTime, activity.Type))

        activity.CalculateUID()
        return activity

    def DownloadActivity(self, serviceRecord, activity):
        # NOTE tcx have to be gzipped but it actually doesn't
        # https://www.polar.com/accesslink-api/?python#get-tcx
        #tcx_data_raw = requests.get(activity_link + "/tcx", headers=self._api_headers(serviceRecord))
        #tcx_data = gzip.GzipFile(fileobj=StringIO(tcx_data_raw)).read()
        tcx_url = serviceRecord.ServiceData["Transaction-uri"] + "/exercises/{}/tcx".format(activity.ServiceData["ActivityID"])
        response = requests.get(tcx_url, headers=self._api_headers(serviceRecord, {"Accept": "application/vnd.garmin.tcx+xml"}))
        if response.status_code == 404:
            # Transaction was disbanded, all data linked to it will be returned in next transaction
            raise APIException("Transaction disbanded", user_exception=UserException(UserExceptionType.DownloadError))
        try:
            tcx_data = response.text
            activity = TCXIO.Parse(tcx_data.encode('utf-8'), activity)
        except lxml.etree.XMLSyntaxError:
            raise APIException("Cannot recieve training tcx at url: {}".format(tcx_url), user_exception=UserException(UserExceptionType.DownloadError))
        return activity

    def SynchronizationComplete(self, serviceRecord):
        # Transaction should be commited to make access to next data possible
        self._commit_transaction(serviceRecord)

    def DeleteCachedData(self, serviceRecord):
        # Nothing to delete
        pass

    def DeleteActivity(self, serviceRecord, uploadId):
        # Not supported
        pass

    def UploadActivity(self, serviceRecord, activity):
        # Not supported
        pass
