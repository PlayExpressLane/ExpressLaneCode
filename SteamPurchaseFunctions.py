import stripe
import boto3
import json
import requests
import uuid

# import base64

client = boto3.client('dynamodb')
cognito = boto3.client('cognito-idp', 'us-east-2')
# Create a Secrets Manager client
session = boto3.session.Session()
client_secrets = boto3.client('secretsmanager')

stripe.api_key = (json.loads(client_secrets.get_secret_value(SecretId='Stripe_Secret', )['SecretString'])['secret_id'])


def retrieve_sub(event, context):
    user_attributes = cognito.get_user(AccessToken=event.get('access_token'))['UserAttributes']
    user_sub = 'None'
    for i in user_attributes:
        if i['Name'] == 'sub':
            print('found sub')
            user_sub = i['Value']
            break
    return user_sub


### retrieve customer ###  
def retrieve_customer(event, context):
    # Looks for the customer in the Customer_Table to get his customer ID for a stripe purchase
    queried_customer = client.get_item(
        TableName='Customer_Table',
        Key={
            'id': {
                'S': (retrieve_sub(event, context))
            }
        },
    )
    # Checks if the customer id associated with the player's account exists  
    if 'Item' in queried_customer:

        # If the customer is in the database, his stripe customer ID is returned  
        customer_id = queried_customer['Item']['customer_id']['S']
        print('customer already exists: ' + (customer_id))

    # If the customer isn't in the database, an account is created for him and added to the database  
    else:
        new_stripe_customer = stripe.Customer.create(
            name=(retrieve_sub(event, context)),
        )
        customer_id = getattr((new_stripe_customer), 'id')

        updated_table = client.put_item(
            TableName='Customer_Table',
            Item={
                "id": {
                    "S": (retrieve_sub(event, context))
                },
                "customer_id": {
                    "S": (customer_id)
                }
            }
        )

    return customer_id


### retrieve player inventory ###  
def retrieve_player_inventory(event, context):
    # Looks for the customer in the Customer_Table to get his customer ID for a stripe purchase
    queried_player = client.get_item(
        TableName='player_inventory',
        Key={
            'id': {
                'S': (retrieve_sub(event, context))
            }
        },
    )
    # Checks if the customer id associated with the player's account exists  
    if 'Item' in queried_player:

        # If the customer is in the database, his stripe customer ID is returned  
        player_inventory = queried_player

    # If the player isn't in the database, an account is created for him and added to the database  
    else:
        updated_table = client.put_item(
            TableName='player_inventory',
            Item={
                "id": {
                    "S": (retrieve_sub(event, context))
                },
            }
        )
        player_inventory = {'Item': {'id': {'S': (event.get('user_sub'))}}}

    return player_inventory


def get_balance(event, context):
    # Looks for the customer in the Customer_Table to get his customer ID for a stripe purchase
    queried_customer = client.get_item(
        TableName='PlayerSimpCoinTable',
        Key={
            'id': {
                'S': (retrieve_sub(event, context))
            }
        },
    )

    # Checks if the customer id associated with the player's account exists  
    if 'Item' in queried_customer:

        # If the customer is in the database, his stripe customer ID is returned  
        str_current_balance = queried_customer['Item']['balance']['N']

    # If the player isn't in the database, an item is created with 0 simpcoin for his sub_id  
    else:
        updated_table = client.put_item(
            TableName='PlayerSimpCoinTable',
            Item={
                "id": {
                    "S": (retrieve_sub(event, context))
                },
                "balance": {
                    "N": ("0")
                }
            }
        )
        str_current_balance = "0"
    return str_current_balance


### Create Charge ###  
def create_charge(event, context):
    # gets or creates the customer's id from his user_sub in the Customer_Table database
    customer_id = retrieve_customer(event, context)

    # Gets the Item from the catalogue that the player wants to purchase
    item_to_purchase = client.get_item(
        TableName='SimpCoinCatalogue',
        Key={
            'id': {
                'S': event.get("product_id")
            }
        },
    )

    # Gets the price_id of the item the player wants to purchase from the DynamoDB database
    price_id = item_to_purchase['Item']['price_id']['S']

    # Retrieves the price of the item the player wants to buy from the stripe database
    item_price = getattr((stripe.Price.retrieve(price_id)), 'unit_amount')
    item_currency = getattr((stripe.Price.retrieve(price_id)), 'currency')
    print(item_price)

    # Checks if a payment method was included  
    if "payment_method" in event:
        print("a payment method is valid")
        # If the customer provided a saved payment method, that payment method is charged
        payment_method_id = event.get("payment_method")

        print(payment_method_id)
        # creates the charge    
        stripe_payment_intent = stripe.PaymentIntent.create(
            amount=(item_price),
            currency=(item_currency),
            payment_method_types=["card"],
            confirm=True,
            customer=(customer_id),
            payment_method=(payment_method_id),
        )

        print(stripe_payment_intent)

    else:
        print("there is no payment method")
        card_data = event.get("card_data")
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": card_data['number'],
                "exp_month": card_data['exp_month'],
                "exp_year": card_data['exp_year'],
                "cvc": card_data['cvc'],
            },
        )
        payment_method_id = payment_method['id']

        if event.get("save_payment_method") == True:
            print('saving payment method')
            stripe_payment_intent = stripe.PaymentIntent.create(
                amount=(item_price),
                currency=(item_currency),
                payment_method_types=["card"],
                confirm=True,
                customer=(customer_id),
                payment_method=(payment_method_id),
                setup_future_usage=('on_session'),
            )
        else:
            print('not saving payment method')
            stripe_payment_intent = stripe.PaymentIntent.create(
                amount=(item_price),
                currency=(item_currency),
                payment_method_types=["card"],
                confirm=True,
                customer=(customer_id),
                payment_method=(payment_method_id),
            )

        # Checks if charge succeeded; if so, add SimpCoin to player's account
    print(getattr((stripe_payment_intent), 'status'))
    status = getattr((stripe_payment_intent), 'status')
    if (getattr((stripe_payment_intent), 'status')) == 'succeeded':

        # Looks for the customer in the Customer_Table to get his customer ID for a stripe purchase
        queried_customer = client.get_item(
            TableName='PlayerSimpCoinTable',
            Key={
                'id': {
                    'S': (retrieve_sub(event, context))
                }
            },
        )

        # Checks if the customer id associated with the player's account exists  
        if 'Item' in queried_customer:

            # If the customer is in the database, his stripe customer ID is returned  
            str_current_balance = queried_customer['Item']['balance']['N']
            print('customer already exists: ' + (customer_id))

        # If the player isn't in the database, an item is created with 0 simpcoin for his sub_id  
        else:
            updated_table = client.put_item(
                TableName='PlayerSimpCoinTable',
                Item={
                    "id": {
                        "S": (retrieve_sub(event, context))
                    },
                    "balance": {
                        "N": ("0")
                    }
                }
            )
            str_current_balance = "0"

        # Gets the current balance of the player that is purchasing the SimpCoin
        str_current_balance = (client.get_item(
            TableName='PlayerSimpCoinTable',
            Key={
                'id': {
                    'S': (retrieve_sub(event, context))
                }
            },
        ))['Item']['balance']['N']
        # Converts the string_current_balance into an int
        current_balance = int(str_current_balance)
        # Gets the price_id of the item the player wants to purchase from the DynamoDB database
        balance_to_add = int(item_to_purchase['Item']['simpcoin']['N'])
        new_balance = current_balance + balance_to_add

        # updates table to new balance for the player who bought the SimpCoin
        updated_table = client.put_item(
            TableName='PlayerSimpCoinTable',
            Item={
                "id": {
                    "S": (retrieve_sub(event, context))
                },
                "balance": {
                    "N": str(new_balance)
                }
            }
        )

    return status


### Create payment method ###  
def create_payment_method(event, context):
    # gets or creates the customer's id from his user_sub in the Customer_Table database
    customer_id = retrieve_customer(event, context)

    card_data = event.get("card_data")
    # creates the payment method from the provided card info
    payment_method = stripe.PaymentMethod.create(
        type="card",
        card={
            "number": card_data['number'],
            "exp_month": card_data['exp_month'],
            "exp_year": card_data['exp_year'],
            "cvc": card_data['cvc'],
        },
    )
    payment_method_id = payment_method['id']

    # attaches the created payment method to a customer
    stripe.PaymentMethod.attach(
        payment_method_id,
        customer=customer_id,
    )
    return payment_method


#### list payment methods ###  
def list_payment_methods(event, context):
    # gets or creates the customer's id from his user_sub in the Customer_Table database
    customer_id = retrieve_customer(event, context)

    # Lists the customer's payment methods
    payment_methods = stripe.Customer.list_payment_methods(
        customer_id,
        type="card",
    )["data"]

    payment_method_ids = []

    #  for i in payment_methods:
    #    payment_method_ids.append(i['id'])

    return payment_methods


### delete payment method ###
def delete_payment_method(event, context):
    stripe.PaymentMethod.detach(
        event.get('payment_method'),
    )
    return None


def retrieve_main_store_listings(event, context):
    # Gets the item ids from the store
    store_item_ids = client.get_item(
        TableName='item_stores_Table',
        Key={
            'id': {
                'S': "main_store"
            }
        },
    )['Item']['Items']['SS']
    # print(store_item_ids)

    # Loops through the store item ids and turns them into a list of dictionaries to input into the batch_get_items
    dict_store_items = []
    for i in store_item_ids:
        dict_store_items.append({'item_key': {'S': i}})
    print(dict_store_items)

    # Gets pricing and other info for each item from the store ids
    store_items = client.batch_get_item(
        RequestItems={
            'Store_Catalogue': {
                # 'Keys': [{'item_key': {'S':'3329eef8-30a1-4d6e-a50f-19dc868499e9'}}]
                'Keys': dict_store_items
            }
        },
    )

    return store_items


def purchase_store_item(event, context):
    status = 'failed'

    # gets the player's simp coin balance
    sc_balance = int(get_balance(event, context))
    # retrieves the price of the item the player wants to purchase
    item_id = (event.get("item_to_purchase"))
    item_info = (client.get_item(
        TableName='Store_Catalogue',
        Key={
            'item_key': {
                'S': item_id
            }
        },
    ))['Item']
    item_type = (item_info)['type']['S']
    print(item_type)
    price = int((item_info)['sc_price']['N'])

    player_inventory = retrieve_player_inventory(event, context)
    print(player_inventory)

    # Checks if the player already has the item in his inventory
    if not item_id in player_inventory['Item'][item_type]['SS']:
        print(player_inventory['Item'][item_type])
        print('item player is trying to buy is not already in his inventory')

        # Checks if customer has enough to purchase the item
        if sc_balance >= price:
            print(sc_balance)
            new_balance = (sc_balance - price)
            print(new_balance)

            # deducts simp coin from the player's balance in the database
            updated_table = client.put_item(
                TableName='PlayerSimpCoinTable',
                Item={
                    "id": {
                        "S": (retrieve_sub(event, context))
                    },
                    "balance": {
                        "N": str(new_balance)
                    }
                }
            )

            # checks if the player has an inventory list for the item type
            if item_type in player_inventory['Item']:
                current_invt_sect = (player_inventory)['Item'][item_type]['SS']
                current_invt_sect.append(item_id)
            else:
                current_invt_sect = [item_id]
            updated_table = client.update_item(
                TableName='player_inventory',
                Key={
                    "id": {"S": (retrieve_sub(event, context))},
                    # "balance": {"N": str(new_balance)}
                },
                AttributeUpdates={
                    (item_type): {'Value': {"SS": current_invt_sect}}
                }
            )
            status = 'succeeded'
    return status


def give_player_simpcoin(event, context):
    item_to_purchase = event.get('item_to_purchase')
    # Looks for the customer in the Customer_Table to get his customer ID for a stripe purchase
    queried_customer = client.get_item(
        TableName='PlayerSimpCoinTable',
        Key={
            'id': {
                'S': event.get("user_sub")
            }
        },
    )

    # Checks if the customer id associated with the player's account exists  
    if 'Item' in queried_customer:

        # If the customer is in the database, his stripe customer ID is returned  
        str_current_balance = queried_customer['Item']['balance']['N']

    # If the player isn't in the database, an item is created with 0 simpcoin for his sub_id  
    else:
        updated_table = client.put_item(
            TableName='PlayerSimpCoinTable',
            Item={
                "id": {
                    "S": event.get("user_sub")
                },
                "balance": {
                    "N": ("0")
                }
            }
        )
        str_current_balance = "0"

    # Gets the current balance of the player that is purchasing the SimpCoin
    str_current_balance = (client.get_item(
        TableName='PlayerSimpCoinTable',
        Key={
            'id': {
                'S': event.get("user_sub")
            }
        },
    ))['Item']['balance']['N']
    # Converts the string_current_balance into an int
    current_balance = int(str_current_balance)
    # Gets the price_id of the item the player wants to purchase from the DynamoDB database
    balance_to_add = int(item_to_purchase['Item']['simpcoin']['N'])
    new_balance = current_balance + balance_to_add

    # updates table to new balance for the player who bought the SimpCoin
    updated_table = client.put_item(
        TableName='PlayerSimpCoinTable',
        Item={
            "id": {
                "S": event.get("user_sub")
            },
            "balance": {
                "N": str(new_balance)
            }
        }
    )


def purchase_steam_item(event, context):
    steamid = event.get('steamid')
    item_to_purchase = event.get('itemtopurchase')
    language = event.get('language')
    currency = event.get('currency')

    # gets the steam id for the item the player is trying to purchase
    item_steam_id = int(client.get_item(
        TableName='SimpCoinCatalogue',
        Key={'id': {'S': item_to_purchase, }},
        ProjectionExpression='#id',
        ExpressionAttributeNames={
            '#id': 'steam_id'
        }
    )['Item']['steam_id']['N'])

    # creates an order id
    orderid = uuid.uuid4().int & (1 << 64) - 1

    post_json = {
        'key': '01A7869661A52B717532E494AC7346CA',
        'orderid': orderid,
        'steamid': steamid,
        'appid': 2071630,
        'itemcount': 1,
        'language': language,
        'currency': currency,
        'usersession': 'client',
        'itemid[0]': 1000,
        'qty[0]': 1,
        'amount[0]': 1000,
        'description[0]': 'in-game currency',
    }

    response = (requests.post('https://partner.steam-api.com/ISteamMicroTxn/InitTxn/v3/', data=post_json)).json()

    print(response)

    return response


def finalize_steam_transaction(event, context):
    steamid = event.get('steamid')
    appid = event.get('appid')
    orderid = event.get('orderid')

    post_json = {
        'key': '01A7869661A52B717532E494AC7346CA',
        'orderid': orderid,
        'appid': appid
    }

    response = (requests.post('https://partner.steam-api.com/ISteamMicroTxn/FinalizeTxn/v2/', data=post_json)).json()

    if response['response']['result'] == 'OK':
        # get cognito account associated with steam id
        user = client.get_item(
            TableName='Linked_Steam_ids',
            Key={'steam_id': {'S': steamid}}, )
        '''
        user = client.scan(
            TableName='Linked_Steam_ids',
            #ProjectionExpression='steam_id',
            FilterExpression="steam_id = :steam_id",
            ExpressionAttributeValues={":steam_id" : {'S': steamid}},
        )['Items'][0]
        '''
        username = user['Item']['username']['S']
        user_sub = user['Item']['sub']['S']

        # query transaction to find item purchased

        orderid = response['response']['params']['orderid']
        transid = response['response']['params']['transid']

        query_txn_json = {
            'key': '01A7869661A52B717532E494AC7346CA',
            'appid': appid,
            'orderid': orderid,
            'transid': transid
        }

        query_txn_response = (
            requests.get('https://partner.steam-api.com/ISteamMicroTxn/QueryTxn/v2/', params=query_txn_json)).json()

        for item in (query_txn_response['response']['params']['items']):
            current = str(item['itemid'])

            # query dynamodb to find simpcoin pack associated with purchased item id
            new_item = {"Item": (client.scan(
                TableName='SimpCoinCatalogue',
                FilterExpression="steam_id = :steam_id",
                ExpressionAttributeValues={":steam_id": {'N': current}},
            )['Items'][0])}
            # get player sub and give player simpcoin
            simpcoin_event = {
                "user_sub": user_sub,
                "item_to_purchase": new_item
            }
            give_player_simpcoin(simpcoin_event, context)

    return response