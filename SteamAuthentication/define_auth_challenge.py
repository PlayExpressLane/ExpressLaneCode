import json


def lambda_handler(event, context):
    if (event['request']['userNotFound']):
        event['response']['failAuthentication'] = True
        event['response']['issueTokens'] = False

    session = event['request']['session']

    if (len(session) > 0 and session[-1]['challengeResult']):
        # The right answer is provided to the challenge is provided - issue tokens to user
        event['response']['failAuthentication'] = False
        event['response']['issueTokens'] = True
        return event

    # in this case we haven't received a correct answer - present new challenge to the user
    event['response']['failAuthentication'] = False
    event['response']['issueTokens'] = False
    event['response']['challengeName'] = 'CUSTOM_CHALLENGE'
    return event