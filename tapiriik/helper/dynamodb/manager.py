# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
from tapiriik.settings import AWS_REGION
import json
import decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from tapiriik.settings import DYNAMO_DB_PREFIX_TABLE
import uuid

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

class DynamoManager:

    _AWS_REGION = AWS_REGION
    _resource = None
    _table = None
    _table_name = None
    _response = None

    _batcher = None

    def __init__(self):
        print("-----[ INITIALIZE A NEW DYNAMODB MANAGER ]-----")
        self._AWS_REGION = AWS_REGION

        # Create DYNAMODB client & resource
        self._resource = boto3.resource('dynamodb', region_name=self._AWS_REGION)
        self._client = boto3.client('dynamodb', region_name=self._AWS_REGION)
        print("[Helper DynamoDB]--- Define DynamoDB resource in %s AWS zone" % self._AWS_REGION)

    def get_table(self, table):
        # Change resource table and store it in object
        self._table = self._resource.Table(DYNAMO_DB_PREFIX_TABLE+table)
        self._table_name = DYNAMO_DB_PREFIX_TABLE+table
        print('[Helper DynamoDB]--- Helper is now using %s table' % DYNAMO_DB_PREFIX_TABLE+table)
        return self._table

    def insert(self, table, item, format='json'):
        self.get_table(table)

        filter_expression = Key('id').eq(item['id'])
        projection_expression = "id"
        expression_attribute_names = {}

        response = self._table.scan(
            FilterExpression=filter_expression,
            ProjectionExpression=projection_expression,
            ExpressionAttributeNames=expression_attribute_names
        )

        if len(response['Items']) is 0:
            response = self._table.put_item(Item=item)
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                result = 'Success'
                msg = 'Item created successfully'
            else:
                result = 'Failure'
                msg = 'Failed to create item'

        data = {}
        data['result'] = result
        data['msg'] = msg

        if format is 'json':
            return json.dumps(data)

        return data

    """
        Serie of function to get multiple lines
    """
    def scan(self, filter_expression, projection_expression, expression_attribute_names):
        response = self._table.scan(
            FilterExpression=filter_expression,
            ProjectionExpression=projection_expression,
            ExpressionAttributeNames=expression_attribute_names
        )
        self._response = response
        return response

    def test_process(self):
        print('[Helper DynamoDB]--- Testing Dynamo manager')