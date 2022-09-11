# Functionality

The hamelin strategy script orchestrates the creation of 'fake' arbitrage opportunities by n accounts using the 
'nonce trick', and then uses the https://github.com/ajb/polygon-spam-analysis tool to display the interaction between
the rates of spam transactions and the occurrence of the fake arbitrage opportunities.

# Requirements
## Token and liquidity

Deploy a basic ERC-20 token on polygon, and create two liquidity pools on DEXes using the Uniswap V2 protocol 
(e.g. Quickswap and legacy Sushiswap) paired with matic and another token that has sufficient liquidity to enable 
arbitrage between the pools (e.g. TOKEN/MATIC and TOKEN/DAI or dual TOKEN/MATIC pools). Allocate supplies of matic and 
the token to the accounts that will execute the strategy. It is possible to execute the 
stragegy with existing tokens and pools, but is not recommended since the fake arbitrage are more likely to fail due to
changes in price and liquidity from other trades.

## Dependencies

- npm
- git
- python3 (with brownie, pandas, and matplotlib packages)
- polygon rpc provider (e.g. https://rpc.ankr.com/polygon)
- polygonscan api token (https://polygonscan.com/apis)

## Setup

- 'git clone https://github.com/GrimmBrothers/Hamelin'
- 'brownie networks modify polygon-main host={rpc url} explorer={https://api.polygonscan.com/api}'
- import accounts to brownie (e.g. 'brownie accounts import hamelin1 '{keystore file}''')
- edit the top of hamelin-strategy.py with your own parameters / list of accounts

On running hamelin-strategy.py succesfully, the output of the spam analysis will be in the directory 'out/'.
