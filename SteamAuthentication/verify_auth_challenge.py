import json
import requests

# ExpressLane PlayTest ID
appid = 2314120


# ExpressLane App ID
# appid = 2071630

def lambda_handler(event, context):
    try:
        challenge = event['request']['privateChallengeParameters']['challenge']

    except:
        event['response']['answerCorrect'] = False
        return event

    # Check if challenge is met

    # Processes the Steam ticket
    response = (requests.get('https://partner.steam-api.com/ISteamUserAuth/AuthenticateUserTicket/v1/', params=
    {
        'key': '01A7869661A52B717532E494AC7346CA',
        'appid': appid,
        'ticket': (event['request']['challengeAnswer'])

    }
                             )).json()

    try:
        return_value = response['response']['params']['steamid']
    except:
        event['response']['answerCorrect'] = False
        return event

    if return_value == challenge:
        event['response']['answerCorrect'] = True
        return event

    event['response']['answerCorrect'] = False
    return event