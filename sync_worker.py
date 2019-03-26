from datetime import datetime
import os

# I'm trying to track down where some missing seconds are going in the sync process
# Will grep these out of the log at some later date


def worker_message(state, now=datetime.now()):
	print("[Sync_worker]--- PID: %d  | status: %s | at %s" % (os.getpid(), state, now.strftime("%Y-%m-%d %H:%M:%S %Z")))


print("-----[ INITIALIZE SYNC_WORKER ]-----")
worker_message("booting")

from tapiriik.requests_lib import patch_requests_with_default_timeout, patch_requests_source_address
from tapiriik import settings
from tapiriik.database import db, close_connections
from pymongo import ReturnDocument
import sys
import subprocess
import socket
from decimal import *

from tapiriik.helper.dynamodb.manager import DynamoManager
from tapiriik.database.model.sync_workers import Sync_workers
from boto3.dynamodb.conditions import Attr

# Time spent rebooting workers < time spent wrangling Python memory management.
RecycleInterval = 2

oldCwd = os.getcwd()
WorkerVersion = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, cwd=os.path.dirname(os.path.abspath(__file__))).communicate()[0].strip()
os.chdir(oldCwd)


# Function use to update heartbeat (status) of sync_worker document
def sync_heartbeat(heartbeat_rec_id, state, user=None):
	_sync_heartbeat_dynamo_manager = DynamoManager()
	_sync_heartbeat_dynamo_manager.get_table('sync_workers')

	#get item from heartbeat_rec_id
	response = _sync_heartbeat_dynamo_manager._table.get_item(Key={
		# 'Host': 'test'
		'id': heartbeat_rec_id
	})

	my_object = sync_worker.get_item('dict')
	# Update item with new infos
	update_response = _sync_heartbeat_dynamo_manager._table.update_item(
		Key={
			'id': my_object['id']
		},
		UpdateExpression="SET Process = :process, Host= :host, HeartBeat= :heartbeat, Startup= :startup, Version= :version, #Indx= :indx, #Stte= :stt",
		ExpressionAttributeValues={
			':process': Decimal(my_object['Process']),
			':host': my_object['Host'],
			':heartbeat': my_object['HeartBeat'],
			':startup': my_object['Startup'],
			':version': my_object['Version'],
			':indx': Decimal(my_object['Index']),
			':stt': state,
		},
		ExpressionAttributeNames={
			"#Stte": "State",
			"#Indx": "Index",
		},
		ReturnValues='ALL_NEW'
	)


worker_message("initialized")
_dynamo_manager = DynamoManager()
_dynamo_manager.get_table('sync_workers')
# Moved this flush before the sync_workers upsert for a rather convoluted reason:
# Some of the sync servers were encountering filesystem corruption, causing the FS to be remounted as read-only.
# Then, when a sync worker would start, it would insert a record in sync_workers then immediately die upon calling flush - since output is piped to a log file on the read-only FS.
# Supervisor would dutifully restart the worker again and again, causing sync_workers to quickly fill up.
# ...which is a problem, since it doesn't have indexes on Process or Host - what later lookups were based on. So, the database would be brought to a near standstill.
# Theoretically, the watchdog would clean up these records soon enough - but since it too logs to a file, it would crash removing only a few stranded records
# By flushing the logs before we insert, it should crash before filling that collection up.
# (plus, we no longer query with Process/Host in sync_hearbeat)

sys.stdout.flush()
# TODO : replace this query by a find and a new func "update_o_insert"

# Instanciate all object
sync_worker = None

# Get all sync_workers with same host and pgid
filter_expression = Attr('Process').eq(os.getpid()) & Attr('Host').eq(socket.gethostname())
projection_expression = "id, Process, Host, HeartBeat, #Indx, Startup, #Stte, Version, #Usr"
expression_attribute_names = {"#Indx": "Index", "#Stte": "State", "#Usr": "User"}

print("[Sync_worker]--- Looking for sync_worker document : %s | %s" % os.getpid() % socket.gethostname())

response = _dynamo_manager.scan(filter_expression, projection_expression, expression_attribute_names)

if len(response['Items']) > 0:
	# If sync_worker document exists, update it
	for i in response['Items']:
		sync_worker = Sync_workers(i)
		i["Process"] = Decimal(os.getpid()),
		i["Host"] = socket.gethostname(),
		i["HeartBeat"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
		i["Startup"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
		i["Version"] = WorkerVersion,
		i["Index"] = Decimal(settings.WORKER_INDEX),
		i["State"] = "startup"
		sync_worker.set_item(i)


		update_response = _dynamo_manager._table.update_item(
			Key={
				'id': sync_worker.id
			},
			UpdateExpression="SET Process = :process, Host= :host, HeartBeat= :heartbeat, Startup= :startup, Version= :version, Index= :indx, State= :stt",
			ExpressionAttributeValues={
				':process': Decimal(os.getpid()),
				':host': socket.gethostname(),
				':heartbeat': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
				':startup': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
				':version': WorkerVersion,
				':indx': Decimal(settings.WORKER_INDEX),
				':stt': "startup",
			},
			ReturnValues='ALL_NEW'
		)
		sync_worker_dict = sync_worker.get_item('dict')
		sync_worker_id = sync_worker_dict['id']
		print("[Sync_worker]--- Updating sync_worker document : %s" % sync_worker_id)

else:
	sync_worker = Sync_workers({
		"Process": Decimal(os.getpid()),
		"Host": socket.gethostname(),
		"HeartBeat": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
		"Startup":  datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
		"Version": WorkerVersion,
		"Index": Decimal(settings.WORKER_INDEX),
		"State": "startup"
	})
	# TODO : process to insert
	_dynamo_manager.insert('sync_workers', sync_worker.get_item('dict'))
	# Else insert it
	sync_worker_dict = sync_worker.get_item('dict')
	sync_worker_id = sync_worker_dict['id']
	print("[Sync_worker]--- Inserting sync_worker document : %s" % sync_worker_id)

sync_worker_dict = sync_worker.get_item('dict')
sync_worker_id = sync_worker_dict['id']

patch_requests_with_default_timeout(timeout=60)

if isinstance(settings.HTTP_SOURCE_ADDR, list):
	settings.HTTP_SOURCE_ADDR = settings.HTTP_SOURCE_ADDR[settings.WORKER_INDEX % len(settings.HTTP_SOURCE_ADDR)]
	patch_requests_source_address((settings.HTTP_SOURCE_ADDR, 0))

print("[Sync_worker]--- PID : %d" % os.getpid())
print("[Sync_worker]--- Index : %s" % settings.WORKER_INDEX)
print("[Sync_worker]--- Interface : %s" % settings.HTTP_SOURCE_ADDR)

# We defer including the main body of the application till here so the settings aren't captured before we've set them up.
# The better way would be to defer initializing services until they're requested, but it's 10:30 and this will work just as well.
from tapiriik.sync import Sync

sync_heartbeat(sync_worker.get_item("dict")["id"], "ready")

worker_message("ready")

Sync = Sync()
Sync.PerformGlobalSync(heartbeat_callback=sync_heartbeat, version=WorkerVersion)

worker_message("shutting down cleanly")

print("[Sync_worker]--- Deleting sync_worker document : %s" % sync_worker_id)
response = _dynamo_manager._table.delete_item(
	Key={
		'id': sync_worker_id,
	}
)


close_connections()
worker_message("shut down")
print("-----[ ENDING SYNC_WORKER ]-----")
sys.stdout.flush()
