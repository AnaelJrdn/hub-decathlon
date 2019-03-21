# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
from tapiriik.settings import AWS_REGION, DYNAMO_DB_PREFIX_TABLE
import json
from tapiriik.helper.dynamodb.manager import DynamoManager
import importlib
import inspect
from pydoc import locate
""" ***** GOOD TO KNOW *****
__________________________________________________
|PYTHON TYPE                     | DYNAMODB TYPE |
|________________________________|_______________|
|string	                         | String (S)    |
|integer	                     | Number (N)    |
|decimal.Decimal	             | Number (N)    |
|boto3.dynamodb.types.Binary	 | Binary (B)    |
|boolean	                     | Boolean (BOOL)|
|None	                         | Null (NULL)   |
|string set	                     | String Set (SS)
|integer set	                 | Number Set (NS)
|decimal.Decimal set	         | Number Set (NS)
|boto3.dynamodb.types.Binary set | Binary Set (BS)
|list	                         | List (L)      |
|dict	                         | Map (M)       |
-------------------------------------------------- 
"""


def find_table(table):
    try:
        module = importlib.import_module('tapiriik.database.model.{0}'.format(table))
        for x in dir(module):
            obj = getattr(module, x)

            if inspect.isclass(obj):
                return obj
    except ImportError:
        return None

class DynamoInstaller():

    _AWS_REGION= AWS_REGION
    _datamodel_path = "../.."
    _table_list = [
        {
            'delete_before_create': False,
            'table_name': 'sync_worker_stats',
            'file_name': 'sync_worker_stats',
            'class_name': 'Sync_worker_stats'
        },
        {
            'delete_before_create': True,
            'table_name': 'test_anael',
            'file_name': 'test_anael',
            'class_name': 'Test_anael'
        }
    ]
    _dynamodb_manager = None

    def __init__(self):
        print('--- INIT DYNAMODB INSTALL ---')
        self._dynamodb_manager = DynamoManager()

    def list_tables(self, format='json'):
        if format is 'json':
            return self._dynamodb_manager._client.list_tables()

        return self._dynamodb_manager._client.list_tables()

    def create_tables(self):
        print('[Install DynamoDB]--- Creating tables process')
        # Get current table list
        current_tables = self.list_tables()

        for table in self._table_list:

            if table['table_name']:
                prefixed_table_name = DYNAMO_DB_PREFIX_TABLE + table['table_name']
                print('[Install DynamoDB]--- Working on %s' % prefixed_table_name)
                # Get module of current table to import
                module_class = locate('tapiriik.database.model.{0}'.format(table['file_name']))
                # Get class of current table to import
                class_bis = getattr(module_class, table['class_name'])
                # Init dynamic table to import
                instance_class = class_bis({})
                # Get create conf of dynamic table instance
                create_conf = getattr(instance_class, '_create_conf')

                # If conf says "delete before create" and if table exist in db
                if table['delete_before_create'] is True and prefixed_table_name in current_tables['TableNames']:
                    print('[Install DynamoDB]--- Deleting %s' % prefixed_table_name)
                    self.delete_table(table['table_name'])

                # If table doesn't exist in db, create it
                if prefixed_table_name in current_tables['TableNames']:
                    print('[Install DynamoDB]--- Can\'t create %s, table already exist' % prefixed_table_name)
                else:
                    print('[Install DynamoDB]--- Creating %s' % prefixed_table_name)
                    if create_conf:
                        self._dynamodb_manager._resource.create_table(
                            AttributeDefinitions=create_conf['AttributeDefinitions'],
                            TableName=prefixed_table_name,
                            KeySchema=create_conf['KeySchema'],
                            ProvisionedThroughput=create_conf['ProvisionedThroughput']
                        )
        list_tables = self.list_tables()
        print(list_tables)
        print('[Install DynamoDB]--- Ending creating table process')

    def delete_table(self, table, format='json'):
        if table:
            try:
                delete_response = self._dynamodb_manager._client.delete_table(TableName=DYNAMO_DB_PREFIX_TABLE+table)
                if delete_response['TableDescription']['TableStatus'] is 'DELETING':
                    result = 'Success'
                    msg = 'Table is deleting'
                else:
                    result = 'Failure'
                    msg = 'An error occured'
            except:

                result = 'Error'
                msg = 'Script failed to execute'

        response = {}
        response['result'] = result
        response['msg'] = msg

        if format is 'json':
            return json.dumps(response)
        return response

    def process(self):
        self.create_tables()
