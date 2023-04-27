import json
import boto3

dynamodb = boto3.client('dynamodb', region_name='us-east-1')


def lambda_handler(event, context):
    print(event)
    username = event['userName']

    steamid = dynamodb.scan(
        TableName='Linked_Steam_ids',
        FilterExpression='username = :username',
        ExpressionAttributeValues={":username": {'S': username}},
    )['Items'][0]['steam_id']['S']

    event['response']['privateChallengeParameters'] = dict()
    event['response']['privateChallengeParameters']['challenge'] = steamid
    return event
