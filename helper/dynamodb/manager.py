# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
from tapiriik.settings import AWS_SQS_ZONE
import json
import decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
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

class DynamoManager():

    AWS_ZONE = AWS_SQS_ZONE

    BATCH_OPERATION_LIST = [
        'add',
        'delete'
    ]
    _resource = None
    _table = None
    _table_name = None
    _response = None

    _batcher = None

    def __init__(self):
        print("-----[ INITIALIZE A NEW DYNAMODB MANAGER ]-----")
        self.AWS_ZONE = AWS_SQS_ZONE
        self.BATCH_OPERATION_LIST = {
            'add': "_batcher_add",
            'delete': "_batcher_delete"
        }


        # Create DYNAMODB client resource
        self._resource = boto3.resource('dynamodb', region_name=self.AWS_ZONE)
        self._client = boto3.client('dynamodb', region_name=self.AWS_ZONE)
        print("[Helper DynamoDB]--- Define DynamoDB resource in %s AWS zone" % self.AWS_ZONE)

    def get_table(self, table):
        self._table = self._resource.Table(table)
        self._table_name = table
        print('[Helper DynamoDB]--- Helper is now using %s table' % table)
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
        Serie of function to get ultiple lines
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