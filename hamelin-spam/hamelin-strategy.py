from web3 import Web3
import time
import json
import os

def construct_buy(router,swap_path,account,amount,gwei,local_nonce): 
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
          'value':int(amount)
        })
    return tx

def construct_sell(router,swap_path,account,amount,gwei,local_nonce):
    deadline = int(time.time() + 120)
    fun = router.functions.swapExactTokensForETH(
      int(amount),
      int(0.1*amount),
      swap_path,
      account,
      deadline
    )
    tx = fun.buildTransaction({
          'from': account,
          'nonce': local_nonce+1,
          'gasPrice': Web3.toWei(gwei, 'gwei'),
        })
    return tx

def approve_tokens(router,account,amount,local_nonce):
    gas_price =w3.eth.gas_price
    fun = mevg_contract.functions.approve(
        router.address,
        amount
    )
    tx = fun.buildTransaction({
          'from': account,
          'nonce': local_nonce,
          'gasPrice': int(1.1*gas_price),
        })
    signed_tx = w3.eth.account.sign_transaction(tx,private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash

def construct_bundle(router,account,gwei_buy,gwei_sell,amount,local_nonce):
    wmatic = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
    mevg   = "0x74D727e735fC38e5eaba18D96EEB1139B0De3cb4"
    # mevg_contract =w3.eth.contract(mevg,abi=token_abi)
    buy_path  = [wmatic,mevg]
    sell_path = [mevg,wmatic]
    amount_out = router.functions.getAmountsOut(amount,buy_path).call()[1]
    print(amount_out/10**18)
   
    tx1 = construct_buy(router,buy_path,account,amount,gwei_buy,local_nonce)
    tx2 = construct_sell(router,sell_path,account,amount_out,gwei_sell,local_nonce)
    
    signed_tx1 = w3.eth.account.sign_transaction(tx1,private_key)
    signed_tx2 = w3.eth.account.sign_transaction(tx2,private_key)
    
    tx_hash2 = w3.eth.send_raw_transaction(signed_tx2.rawTransaction)
    time.sleep(5)
    tx_hash1 = w3.eth.send_raw_transaction(signed_tx1.rawTransaction)
    
    return tx_hash1,tx_hash2

w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.infura.io/v3/0639876fbdc74775b954fc39ac646a63'))

private_key = "430dd0be323dd127a892072eaccc3e93d0334e266699ff5d404b185803a535ba"
account = "0x6bE6Ca54C41d87F3713b574Af4eacF971f53ee5E"

with open("../ABIs/routerabi.txt","r") as f:
    router_abi = json.load(f)
with open("../ABIs/token_abi.txt","r") as f:
    token_abi = json.load(f)

router = w3.eth.contract("0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",abi=router_abi)
wmatic = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
mevg   = "0x74D727e735fC38e5eaba18D96EEB1139B0De3cb4"

mevg_contract = w3.eth.contract(mevg,abi=token_abi)
gamma =1 
local_nonce = w3.eth.get_transaction_count(account)
amount = 20*10**18
first_block = w3.eth.blockNumber


for i in range(0,2):
    price = w3.eth.gas_price
    gas_price = int(gamma*int(Web3.toWei(price,'gwei')/10**18)+1)
    allowed_amount = mevg_contract.functions.allowance(account,router.address).call()
    if allowed_amount < amount:
        balance = mevg_contract.functions.balanceOf(account).call()
        tx_approve_hash = approve_tokens(router, account,balance,local_nonce)
        w3.eth.wait_for_transaction_receipt(tx_approve_hash.hex())
        print(f"Allowed {balance}")
        local_nonce += 1
    time.sleep(3)
    
    tx1_hash,tx2_hash = construct_bundle(router,account,gas_price,gas_price+10,amount,local_nonce)
    w3.eth.wait_for_transaction_receipt(tx2_hash.hex())
    local_nonce +=2
    
last_block = w3.eth.get_transaction(tx2_hash).blockNumber

os.system(f'START_BLOCK={first_block} END_BLOCK={last_block} node ../detect-spam/index.js')
os.system('mv ../detect-spam/out ./')