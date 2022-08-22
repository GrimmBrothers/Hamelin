---
author:
- Bruno Mazorra, Michael Reynolds
date: July 2022
title: "The Polygon Pied Piper Stategy"
---
<div style="text-align: center;">
    <img src="https://i.imgur.com/vtNxlWz.jpg" width="300" alt="">
</div>

# Summary

We have identified a trading / transaction propagation attack strategy
which, at relatively low cost to an adversary, exposes Polygon PoS to
the following vulnerabilities:

1.  Censorship of user transactions (**medium**)
2.  Denial of service attacks (**medium**)
3.  Drain bots.
3.  Chain halt and shutting down the network (**critical but unlikely**)

The strategy creates visible arbitrage opportunities in the mempool to
incentivise MEV bots to spam arbitrage transactions. Manipulation of
account nonces and the properties of bor client transaction propagation
is used to prevent MEV bots from actually extracting the arbitrage
opportunity, rather the trade reverses at no cost to the strategy user
except for gas fees. This allows an adversary to create a large number
of on-chain spam transactions for minimal cost. In other words, **the
strategy bribes MEV bots to fill Polygon PoS blocks with spam
transactions, without actually paying the bribe**.

# Steps to reproduce

The following is an example of such a strategy that can easily be
deployed on Polygon PoS using a public RPC with minimal capital
requirements:

i)  Choose two popular tokens, for example Matic and DAI, which have
    enough liquidity in forks of the Uniswap V2 protocol which we
    represent as $\texttt{pool}_{V2}$.

ii) Deploy a token $\mathbb T$ and deploy two Uniswap V2 pools
    $\texttt{pool}_1$ and $\texttt{pool}_2$ paired with Matic and Dai
    respecitvely; only a small amount of liquidity is required.

iii) Prepare a set of addresses $\mathcal A$ with Matic to cover gas
     fees, and sufficient Matic / $\mathbb T$ to create trades with.

iv) For each address, construct a buy transaction $\texttt{tx}_1$ in
    $\texttt{pool}_1$ that leaves a triangular arbitrage opportunity of
    value $\delta>>0$ between the three pools.

v)  Increment the address nonce and construct a sell transaction
    $\texttt{tx}_2$ with the quantity of tokens $\mathbb T$ that the
    transaction $\texttt{tx}_1$ will generate, and place a slightly
    higher gas bid.

vi) For each address, broadcast $\texttt{tx}_2$. Wait for
    $\texttt{tx}_2$ to propagate sufficiently, and then broadcast
    $\texttt{tx}_1$.

vii) Go back to step iv).

A python script to reproduce this example of the strategy is given at
the end of this report. (Not in this repo)

# Impact

We ran short tests of the example strategy on Polygon PoS mainnet to
obtain data to establish a proof of concept; it was impossible to use a
private testnet as we were unable to replicate the obfuscated behaviour
of MEV bots on mainnet.  We
generated transactions exclusively **off-chain** with code that is
**private** to us; we did **not** attempt the example strategy with such
volume and order size as to cause a DDoS event or to cause user
transactions to be censored; and we did **not** test the example
strategy with such volume, order size, and for a sustained period as to
impact liveness of the chain.

Figure 1 displays the Polygon spam analysis tool results during testing
of the example strategy using 5 addresses, an order size of 15 matic,
for five iterations separated by 10 seconds; total estimated cost of
execution was 0.5 Matic, where each 'burst' cost 0.1 Matic (gas price
approximately 75 Gwei).


|![](https://i.imgur.com/U13oSVU.png)|
|:--:|
|Where Green line = Number of transactions, Blue line = % Arbitrage transactions (lower bound), Red dots = Fake arbitrage opportunities|

This demonstrates that it was possible to increase the number of spam
transactions in a block from 50 to around 150 (with spikes up to 400)
for five blocks for a cost of 0.1 Matic with gas prices at 75 Gwei. We
therefore anticipate from these results that by increasing the order
size, number of addresses, and volume of trades, it would be possible
for an attacker to fill every block with spam transactions initially at
a price of 0.02 Matic per block given an initial base fee of 75 Gwei,
with later block costs rising with the base fee according to the Polygon
EIP-1559 implementation.

**Put more simply, we anticipate that it is possible to fill an entire
block with spam at 0.75% the cost of using the entire gas limit of a
block.**

# Origin of the issue

It is well known that the transaction propagation mechanism of the bor
client incentivizes spamming to extract MEV opportunities. A fair
assumption is that the mechanism results in transactions landing in a
random block according to a uniform distribution; with transactions
ordered according to gas price within the block they end up in.
Furthermore, it is reasonable to assume that transactions with the same
gas price will be ordered according to arrival time at the elected
validator provided they are valid.

The above strategy works by ensuring the sell transaction
$\texttt{tx}_2$ is propagated fully through the mempool, but is
temporarily invalid since the nonce is too high. Then, after
broadcasting the buy transaction $\texttt{tx}_1$, $\texttt{tx}_2$ only
becomes valid once a validator receives $\texttt{tx}_1$, and since
$\texttt{tx}_2$ has a higher gas price than $\texttt{tx}_2$, it is place
directly after $\texttt{tx}_1$ in most cases.

Now, MEV bots see $\texttt{tx}_1$ as a back-running MEV opportunity, and
spam the network with transactions at the same gas price as
$\texttt{tx}_1$ in an attempt to be positioned directly after it in the
block to extract the MEV. $\texttt{tx}_2$ has a slightly higher gas
price than $\texttt{tx}_1$, so $\texttt{tx}_2$ also appears as another
back-running MEV opportunity, which causes MEV bots to spam the network
to extract the MEV opportunity there as well. However, $\texttt{tx}_2$
doesn't represent a back-running MEV opportunity at all, since
$\texttt{tx}_1$ will be placed directly before $\texttt{tx}_2$ in most
cases!

We have not observed this strategy to work consistently in other EVM
networks, and therefore believe this is unique to Polygon PoS and its
bor client implementation.

# Fix

Different solutions with various trade-offs can solve this problem.

-   **Solution 1:** Introduce a private mempool or Combinatorial auction
    such as Flasbhots (mev-bor).
-   **Solution 2:** Make the strategy widely available to raise
    awareness of this potential attack and wait for searchers to make
    relevant changes to their MEV bot software.
-   **Solution 3:** Change bor client to reject transaction if
    transactions of the same address with $\leq \text{nonce}-1$ are not
    visible in the mempool or in a block.

![](https://i.imgur.com/EAfkSN8.png)

The first solution would allow mev bots to extract the opportunity
without having incentives to spam, reducing the negative externalities
of the attack (and also making the strategy useless). However, making
the mempool private will completely change the Polygon PoS consensus
protocol, and the Flashbots (mev-bor) solution has already been tried
with poor results. Furthermore, both implementations of solution 1 would
require an increase in time between blocks and reduce the throughput of
Polygon PoS. The second solution does not make any technical changes to
Polygon PoS and does not require any sophisticated solutions. However,
before the searchers and developers make the necessary changes to their
bots, adversarial players could exploit these opportunities to attack,
rendering the network publicly exposed to the vulnerabilities listed
above for a non-negligible amount of time. The third solution changes
the user experience, not allowing players to quickly send a bundle of
transactions. The solution would be easy to implement with some minor
changes in the bor client. Also, this solution would immediately prevent
this attack. **In conclusion, the most agnostic thing to do is warn the bot owners and let the system balance itself.**


# Theoretical results

**Random ordering**: Assuming that validator order transactions with sama gas price uniformly random. Furthermore, we assume that all players share the same gas costs and efficiencies for extractin the arbitrage opportunity. If there is a total of $m$ transactions competing for the $ev$ opportunity and $k\leq m$ are sent by the player $P_i$, then the expected payoff is:

$\mathbb E[\Delta b_i] = \frac{k}{m+1}(ev - g m-(k-1)\gamma m) - (1-\frac{k}{m+1})k\gamma m$

Where $g$ is the gas cost of the arbitrage transaction, $m$ is the gas price of the arbitrage opportunity and $\gamma$ the gas costs of the failed arbitrage transactions.
In this setting, one can prove that, in equilibrium, players will consume the gas showed in the following graph.

<div style="text-align: center;">
    <img src="https://i.imgur.com/ctRxNYq.jpg" width="300" alt="">
</div>


# Supporting material/references

1.  [Flashboys 2.0.](https://arxiv.org/abs/1904.05234)
2.  [MEV negative externalities](https://medium.com/flashbots/frontrunning-the-mev-crisis-40629a613752)
3.  [MEV polygon spam](https://twitter.com/bertcmiller/status/1412579402345586696?lang=zh-Hant)
4.  [Polygon spam analysis
    tool](https://github.com/ajb/polygon-spam-analysis)
5.  [Reduce competitive spam by having sentries always send full transactions to validators](https://github.com/maticnetwork/bor/pull/292)

