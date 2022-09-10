# imports

from web3 import Web3
import time
import asyncio
import json

# includes

# account dictionary, format {"public key":"private key",...,"public key":"private key"}
with open("accounts.json", "r") as f:
    accounts = json.load(f)

# Uniswap V2 router ABI
with open("routerabi.txt", "r") as f:
    router_abi = json.load(f)

# ERC20 token ABI
with open("token_abi.txt", "r") as f:
    token_abi = json.load(f)

# Constants

w3 = Web3(Web3.HTTPProvider(""))

univ2_router_address = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
univ2_router = w3.eth.contract(address=univ2_router_address, abi=router_abi)
wmatic_address = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
token_address = ""

token_contract = w3.eth.contract(address=token_address, abi=token_abi)
gamma = 1

# Parameters

# fake order size in Matic
order_size = 15 * 10 ** 18
# iterations of strategy
iterations = 5
# max gas price before executing another iteration
gas_price_limit = 1000
# time between accounts executing strategy
account_wait = 2
# time between iterations
iteration_wait = 10

# initialise transaction,block list,the latest gas price, and blob function bool

transactions = list()
block_attacked = []
latest_gas_price = 0
blob_complete = False


# functions

# construct buy order (before sell order)

def construct_buy(router, swap_path, account, amount, gwei, local_nonce):
    deadline = int(time.time() + 120)
    fun = router.functions.swapExactETHForTokens(
        int(amount),
        swap_path,
        account,
        deadline
    )
    tx = fun.buildTransaction({
        'from': account,
        'nonce': local_nonce,
        'gasPrice': Web3.toWei(gwei, 'gwei'),
        'value': int(amount)
    })
    return tx


# construct sell order after buy order

def construct_sell(router, swap_path, account, amount, gwei, local_nonce):
    deadline = int(time.time() + 120)
    fun = router.functions.swapExactTokensForETH(
        int(amount),
        int(0.1 * amount),
        swap_path,
        account,
        deadline
    )
    tx = fun.buildTransaction({
        'from': account,
        'nonce': local_nonce + 1,
        'gasPrice': Web3.toWei(gwei, 'gwei'),
    })
    return tx


# approve token for account

def approve_tokens(router, account, private_key, amount, local_nonce):
    gas_price = latest_gas_price
    fun = token_contract.functions.approve(
        router.address,
        amount
    )
    tx = fun.buildTransaction({
        'from': account,
        'nonce': local_nonce,
        'gasPrice': int(1.1 * gas_price),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash


# constructs fake arb bundle

async def construct_bundle(router, account, private_key, gwei_buy, gwei_sell, amount, local_nonce):
    buy_path = [wmatic_address, token_address]
    sell_path = [token_address, wmatic_address]
    amount_out = router.functions.getAmountsOut(amount, buy_path).call()[1]
    print(amount_out / 10 ** 18)

    tx1 = construct_buy(router, buy_path, account, amount, gwei_buy, local_nonce)
    tx2 = construct_sell(router, sell_path, account, amount_out, gwei_sell, local_nonce)

    signed_tx1 = w3.eth.account.sign_transaction(tx1, private_key)
    signed_tx2 = w3.eth.account.sign_transaction(tx2, private_key)

    tx_hash2 = w3.eth.send_raw_transaction(signed_tx2.rawTransaction)
    await asyncio.sleep(5)
    tx_hash1 = w3.eth.send_raw_transaction(signed_tx1.rawTransaction)

    return tx_hash1, tx_hash2


# function to test if a tx has been included in a block

def test_mined(tx):
    try:
        w3.eth.get_transaction(tx)
    except (Exception,):
        return True
    else:
        return False


# creates fake arb for account

async def hamelin_address(account, private_key, i):
    await asyncio.sleep(account_wait * i)
    try:
        nonce = w3.eth.get_transaction_count(account)
        price = int(latest_gas_price)
        print(account)
        gas_price = int(gamma * int(Web3.toWei(price, 'gwei') / 10 ** 18) + 1)
        allowed_amount = token_contract.functions.allowance(account, univ2_router.address).call()
        if allowed_amount < order_size:
            balance = token_contract.functions.balanceOf(account).call()
            tx_approve_hash = approve_tokens(univ2_router, account, private_key, balance, nonce)
            w3.eth.wait_for_transaction_receipt(tx_approve_hash)
            print(f"Allowed {balance}")
            nonce += 1
            await asyncio.sleep(3)
        tx2_hash = '0x'
        tx1_hash = '0x'
        while test_mined(tx2_hash):
            tx1_hash, tx2_hash = await construct_bundle(univ2_router, account, private_key, gas_price, gas_price + 10,
                                                        order_size, nonce)
            await asyncio.sleep(2)
            price = latest_gas_price
            if price > gas_price * 1.125:
                gas_price = int(gamma * int(Web3.toWei(price, 'gwei') / 10 ** 18) + 1)
            else:
                gas_price = int(gas_price * 1.125)
        w3.eth.wait_for_transaction_receipt(tx2_hash)
        transactions.append(tx1_hash.hex())
        transactions.append(tx2_hash.hex())
        nonce += 2
    except Exception as err:
        print(f"Error caused by {account}\n error {err}")


# gets the current gas price

async def get_gas_price():
    return w3.eth.gas_price


# gets current gas price and updates latest_gas_price globally

async def get_latest_gas_price():
    try:
        global latest_gas_price

        latest_gas_price = await get_gas_price()

        latest_gas_price = latest_gas_price * 2

        print(f"Latest gas price: {latest_gas_price}")
        return latest_gas_price
    except Exception as err:
        print(f"There was an error getting the latest gas price {err}")


# creates globally updating gas price

async def gas_price_heartbeat():
    while not blob_complete:
        await get_latest_gas_price()
        await asyncio.sleep(2)


# iteration function

async def blob():
    for i in range(0, iterations):
        # gas price limit in gwei
        price = latest_gas_price
        gas_price = int(gamma * int(Web3.toWei(price, 'gwei') / 10 ** 18) + 1)
        if gas_price < gas_price_limit:
            # loop = asyncio.get_event_loop()
            await asyncio.gather(
                *[hamelin_address(account, accounts[account], i) for i, account in enumerate(accounts)])
        await asyncio.sleep(iteration_wait)
    global blob_complete
    blob_complete = True
    return blob_complete


# main function

async def main():
    f1 = loop.create_task(gas_price_heartbeat())
    f2 = loop.create_task(blob())
    await asyncio.wait([f1, f2])


# run main function

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())
loop.close()
