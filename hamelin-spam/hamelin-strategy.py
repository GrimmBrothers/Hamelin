# Imports
from brownie import accounts, Contract, network
import time
import os
import asyncio
import json
import pandas as pd
from matplotlib import pyplot as plt

# Constants
network.connect('polygon-main')
network.is_connected()
w3 = network.web3

# export etherscan api token
os.environ["POLYGONSCAN_TOKEN"] = "api token"

# load contracts and create w3 versions
wmatic_address = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
univ2 = Contract.from_explorer("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff")
token = Contract.from_explorer("token address")
univ2_router = w3.eth.contract(address=univ2.address, abi=univ2.abi)
token_contract = w3.eth.contract(address=token.address, abi=token.abi)

# Parameters
order_size = 5 * 10 ** 18
iterations = 5
gas_price_limit = 1000
account_wait = 2
iteration_wait = 10
gamma = 1

# initialise transaction, block list, latest gas price, and blob function bool
transactions = list()
block_attacked = []
latest_gas_price = 0
blob_complete = False

# accounts
account = accounts.load('hamelin1')
accounts_list = {account.address: account.private_key}


# functions
def construct_buy(router, swap_path, _account, amount_in, amount_out, gwei, local_nonce):
    deadline = int(time.time() + 120)
    fun = router.functions.swapExactETHForTokens(
        int(amount_out),
        swap_path,
        _account,
        deadline
    )
    tx = fun.buildTransaction({
        'from': _account,
        'nonce': local_nonce,
        'gasPrice': w3.toWei(gwei, 'gwei'),
        'value': int(amount_in)
    })
    return tx


def construct_sell(router, swap_path, _account, amount_in, amount_out, gwei, local_nonce):
    deadline = int(time.time() + 120)
    fun = router.functions.swapExactTokensForETH(
        int(amount_in),
        int(0.1 * amount_out),
        swap_path,
        _account,
        deadline
    )
    tx = fun.buildTransaction({
        'from': _account,
        'nonce': local_nonce + 1,
        'gasPrice': w3.toWei(gwei, 'gwei'),
    })
    return tx


def approve_tokens(router, _account, private_key, amount, local_nonce):
    gas_price = latest_gas_price
    fun = token_contract.functions.approve(
        router.address,
        amount
    )
    tx = fun.buildTransaction({
        'from': _account,
        'nonce': local_nonce,
        'gasPrice': int(1.1 * gas_price),
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash


async def construct_bundle(router, _account, private_key, gwei_buy, gwei_sell, amount, local_nonce):
    buy_path = [wmatic_address, token.address]
    sell_path = [token.address, wmatic_address]
    amount_out = router.functions.getAmountsOut(amount, buy_path).call()[1]
    print(amount_out / 10 ** 18)

    tx1 = construct_buy(router, buy_path, _account, amount, amount_out, gwei_buy, local_nonce)
    print("Constructed buy")
    tx2 = construct_sell(router, sell_path, _account, amount_out, amount, gwei_sell, local_nonce)
    print("Constructed sell")

    signed_tx1 = w3.eth.account.sign_transaction(tx1, private_key)
    signed_tx2 = w3.eth.account.sign_transaction(tx2, private_key)

    tx_hash2 = w3.eth.send_raw_transaction(signed_tx2.rawTransaction)
    await asyncio.sleep(5)
    tx_hash1 = w3.eth.send_raw_transaction(signed_tx1.rawTransaction)

    return tx_hash1, tx_hash2


def test_mined(tx):
    try:
        w3.eth.get_transaction(tx)
    except (Exception,):
        return True
    else:
        return False


async def hamelin_address(_account, private_key, i):
    await asyncio.sleep(account_wait * i)
    try:
        nonce = w3.eth.get_transaction_count(_account)
        price = int(latest_gas_price)
        print(_account)
        gas_price = int(gamma * int(w3.toWei(price, 'gwei') / 10 ** 18) + 1)
        allowed_amount = token_contract.functions.allowance(_account, univ2_router.address).call()
        if allowed_amount < order_size:
            balance = token_contract.functions.balanceOf(_account).call()
            tx_approve_hash = approve_tokens(univ2_router, _account, private_key, balance, nonce)
            w3.eth.wait_for_transaction_receipt(tx_approve_hash)
            print(f"Allowed {balance}")
            nonce += 1
            await asyncio.sleep(3)
        # while loop
        tx2_hash = '0x'
        tx1_hash = '0x'
        while test_mined(tx2_hash):
            tx1_hash, tx2_hash = await construct_bundle(univ2_router, _account, private_key, gas_price, gas_price + 10,
                                                        order_size, nonce)
            await asyncio.sleep(2)
            price = latest_gas_price
            if price > gas_price * 1.125:
                gas_price = int(gamma * int(w3.toWei(price, 'gwei') / 10 ** 18) + 1)
            else:
                gas_price = int(gas_price * 1.125)
        w3.eth.wait_for_transaction_receipt(tx2_hash)
        transactions.append(tx1_hash.hex())
        transactions.append(tx2_hash.hex())
        nonce += 2
    except Exception as err:
        print(f"Error caused by {_account}\n error {err}")


async def get_block(transaction):
    return w3.eth.get_transaction(transaction).blockNumber


async def get_block_attacked(txs):
    for tx_hash in txs:
        block = await get_block(tx_hash)
        block = int(block)
        block_attacked.append(block)
    return block_attacked


# get the latest gas price
async def get_gas_price():
    return w3.eth.gas_price


async def get_latest_gas_price():
    try:
        global latest_gas_price

        old_gas_price = latest_gas_price

        latest_gas_price = await get_gas_price()

        latest_gas_price = latest_gas_price * 2

        if latest_gas_price != old_gas_price:
            print(f"Latest gas price: {latest_gas_price}")
        return latest_gas_price
    except Exception as err:
        print(f"There was an error getting the latest gas price {err}")


async def gas_price_heartbeat():
    while not blob_complete:
        await get_latest_gas_price()
        await asyncio.sleep(2)


async def blob():
    for i in range(0, iterations):
        # gas price limit in gwei
        price = latest_gas_price
        gas_price = int(gamma * int(w3.toWei(price, 'gwei') / 10 ** 18) + 1)
        if gas_price < gas_price_limit:
            await asyncio.gather(
               *[hamelin_address(_account, accounts_list[_account], i) for i, _account in enumerate(accounts_list)])
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

print("sleep")
time.sleep(30)
print("awake")

asyncio.run(get_block_attacked(transactions))

last_block = max(block_attacked) + 3
first_block = min(block_attacked) - 3

# calculate stats
os.system(f'START_BLOCK={first_block} END_BLOCK={last_block} node ../detect-spam/index.js')
block_attacked.sort()
print(block_attacked)
with open(f"./out/{first_block}-{last_block}/blocks_attacked", "w") as f:
    json.dump(block_attacked, f)

df = pd.read_csv(f"./out/{first_block}-{last_block}/blocks.csv")

attack_rate = [df[df['block'] == block]['total'] for block in block_attacked]
blocks_plot = list(df['block'])
rate = list(df['total'])

plt.plot(blocks_plot, rate, label="Spam", color="green")
plt.scatter(block_attacked, attack_rate, s=80, marker=(5, 0), color="red")
plt.xlabel('Blocks')
plt.ylabel('Number of tx')

plt.savefig(f'./out/{first_block}-{last_block}/block-total.png')

attack_rate = [df[df['block'] == block]['rate'] for block in block_attacked]
blocks_plot = list(df['block'])
rate = list(df['rate'])

plt.plot(blocks_plot, rate, label="Spam", color="blue")
plt.scatter(block_attacked, attack_rate, s=80, marker=(5, 0), color="red")
plt.xlabel('Blocks')
plt.ylabel('Rate of spam')
plt.savefig(f'./out/{first_block}-{last_block}/block-rate.png')
