# Imports

from web3 import Web3
import time
import os
import asyncio
import json
import pandas as pd
from matplotlib import pyplot as plt

# includes

with open("../accounts.json", "r") as f:
    accounts = json.load(f)
with open("../ABIs/routerabi.txt", "r") as f:
    router_abi = json.load(f)
with open("../ABIs/token_abi.txt", "r") as f:
    token_abi = json.load(f)

# Constants

# w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.infura.io/v3/0639876fbdc74775b954fc39ac646a63'))

w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/polygon'))

univ2_router_address = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
univ2_router = w3.eth.contract(address=univ2_router_address, abi=router_abi)
wmatic_address = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
mevg_address = "0x74D727e735fC38e5eaba18D96EEB1139B0De3cb4"

mevg_contract = w3.eth.contract(address=mevg_address, abi=token_abi)
gamma = 1

# Parameters

order_size = 15 * 10 ** 18
iterations = 5
gas_price_limit = 1000
account_wait = 2
iteration_wait = 10

# initialise transaction,block list,the latest gas price, and blob function bool

transactions = list()
block_attacked = []
latest_gas_price = 0
blob_complete = False


# functions

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


def approve_tokens(router, account, private_key, amount, local_nonce):
    gas_price = latest_gas_price
    fun = mevg_contract.functions.approve(
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


async def construct_bundle(router, account, private_key, gwei_buy, gwei_sell, amount, local_nonce):
    buy_path = [wmatic_address, mevg_address]
    sell_path = [mevg_address, wmatic_address]
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


def test_mined(tx):
    try:
        w3.eth.get_transaction(tx)
    except (Exception,):
        return True
    else:
        return False


async def hamelin_address(account, private_key, i):
    await asyncio.sleep(account_wait * i)
    try:
        nonce = w3.eth.get_transaction_count(account)
        price = int(latest_gas_price)
        print(account)
        gas_price = int(gamma * int(Web3.toWei(price, 'gwei') / 10 ** 18) + 1)
        allowed_amount = mevg_contract.functions.allowance(account, univ2_router.address).call()
        if allowed_amount < order_size:
            balance = mevg_contract.functions.balanceOf(account).call()
            tx_approve_hash = approve_tokens(univ2_router, account, private_key, balance, nonce)
            w3.eth.wait_for_transaction_receipt(tx_approve_hash)
            print(f"Allowed {balance}")
            nonce += 1
            await asyncio.sleep(3)
        # while loop
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

        latest_gas_price = await get_gas_price()

        latest_gas_price = latest_gas_price * 2

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
        gas_price = int(gamma * int(Web3.toWei(price, 'gwei') / 10 ** 18) + 1)
        if gas_price < gas_price_limit:
            # loop = asyncio.get_event_loop()
            await asyncio.gather(
                *[hamelin_address(account, accounts[account], i) for i, account in enumerate(accounts)])
            # results = loop.run_until_complete(group)
            # local_nonce = {address:
            #            w3.eth.get_transaction_count(address) for address in accounts.keys()
            #     }
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

# make sure npm is installed
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
