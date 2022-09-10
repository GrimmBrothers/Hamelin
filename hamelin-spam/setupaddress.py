from brownie import Contract, network,accounts
import json
from web3 import Web3
from django.template import base

def approve_tokens(router, account, private_key, amount, local_nonce):
    gas_price = w3.eth.gas_price
    fun = token.functions.approve(
        router,
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



with open("../ABIs/token_abi.txt","r") as f:
    token_abi = json.load(f)


w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.infura.io/v3/0639876fbdc74775b954fc39ac646a63'))
network.connect('Mainnet')
if network.chain.id == 137:
    router = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
    mevg   = "0x74D727e735fC38e5eaba18D96EEB1139B0De3cb4"

    token = w3.eth.contract(mevg,abi = token_abi)
    #token = Contract.from_abi("MEVG",mevg,abi = token_abi)

    with open("../accounts.json","r") as f:
        account_dict = json.load(f)

    base_account = accounts.add(list(account_dict.values())[0])
    list_accounts = [accounts.add(private_key) for private_key in account_dict.values()]

    for account in account_dict:
        if account != base_account.address:
            base_account.transfer(account,15*10**18)
            #token.transfer(account,1000*10**18,{'from':base_account})
            
    # for acc in list_accounts:
    #     if acc.address!=base_account.address:
    #         local_nonce = w3.eth.getTransactionCount(acc.address)
    #         approve_tokens(router, acc.address, acc.private_key, 1000*10**18, local_nonce)

