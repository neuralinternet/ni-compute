import argparse
import os
import json
import asyncio
import threading
import time
import bittensor as bt
from compute import validator_permit_stake
from compute.axon import ComputeSubnetSubtensor
from compute.axon import ComputeSubnetAxon, ComputeSubnetSubtensor
from compute.wandb.wandb import ComputeWandb  # Importing ComputeWandb
from compute.protocol import POG, Allocate
class watchtower:
    def __init__(self, config):
        self.config = config
        self.metagraph = self.get_metagraph() # Retrieve metagraph state
        self.subtensor = ComputeSubnetSubtensor(config=self.config)
        self.validators = self.get_valid_validator_hotkeys()
        self.wallet = bt.wallet(config=self.config)
        self.wandb = ComputeWandb(self.config, self.wallet, os.path.basename(__file__))
    def get_metagraph(self):
        """Retrieves the metagraph from subtensor."""
        subtensor = bt.subtensor(config=self.config)
        return subtensor.metagraph(self.config.netuid)
    def get_metagraph_uids(self):
        return self.metagraph.uids.tolist()
    
    def get_valid_validator_hotkeys(self):
        valid_uids = []
        for index, uid in enumerate(self.get_metagraph_uids()):
            if self.metagraph.total_stake[index] > validator_permit_stake:
                valid_uids.append(uid)
        valid_hotkeys = []
        for uid in valid_uids:
            neuron = self.subtensor.neuron_for_uid(uid, self.config.netuid)
            hotkey = neuron.hotkey
            valid_hotkeys.append(hotkey)
        return valid_hotkeys
    
    def get_queryable(self):
        miners = self.metagraph.hotkeys
        return miners
    
    async def exchange_miner_key_auth(self, miner_axon, auth_key):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            dendrite = bt.dendrite(wallet=self.wallet)
            try:
                authority_exchange = {"authorized_key": auth_key}
                res = await dendrite(miner_axon, Allocate(checking=False,authority_exchange=authority_exchange), timeout=30)
                bt.logging.info(f"Exchanged miner key auth with {miner_axon} , and got response {res}")
                # print only the axons that got non empty json on response

                for index, r in enumerate(res):
                    if r != {}:
                        print(f"Miner {index} - {miner_axon[index].hotkey} response: {r}")
                # await asyncio.sleep(3000)
                return True
            except Exception as e:
                bt.logging.error(f"Attempt {attempt}: Failed to exchange miner key auth with {miner_axon} - {e}")
                if attempt < max_retries:
                    await asyncio.sleep(3)
                else:
                    return False
            finally:
                await dendrite.aclose_session()
    
    async def exchange_miners_key_auth_exchange(self,miners_keys, auth_key):
        axons = self.metagraph.axons
        axons = [axon for axon in axons if axon.hotkey in ["5FQseA4n4QsLz9Yw7LbodhM2p514bq3kKM9FiUZE8iGMXzSR","5DHe1a3tUhB9fo8hBAzpFcYEHrq8QiYvkCcGvjjRe9sHpjwW","5DUQqHM6EYH9kWQJ52747iFJEiL9rTuEsCHh7L1sVCeeToGi","5CiYU3vsgugH9RnDHJ31eawhxEigf9L11Sr2oCekHMjrBPht"]]
        # axons = [axon for axon in axons if axon.hotkey in miners_keys]
        # for axon in axons:
        await self.exchange_miner_key_auth(axons, auth_key)

    async def give_validator_pog_access(self,validator_hotkey):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            dendrite = None
            try:
                for axon in self.metagraph.axons:
                    if axon.hotkey == validator_hotkey:
                        validator_axon = axon
                        break
                dendrite = bt.dendrite(wallet=self.wallet)
                res = await dendrite(validator_axon, POG(pog=True), timeout=30)
                bt.logging.info(f"Successfully gave validator pog access {validator_hotkey} and got response {res}")
                return res.get("status", False)
            except Exception as e:
                bt.logging.error(f"Attempt {attempt}: Failed to give validator pog access {validator_hotkey} {e}")
                if attempt < max_retries:
                    await asyncio.sleep(10)
                else:
                    bt.logging.error(f"All {max_retries} attempts failed for validator {validator_hotkey}")
                return False
            finally:
                if dendrite is not None:
                    await dendrite.aclose_session()

    async def pog_orchastractor(self):
        miners_hotkeys = self.get_queryable()
        validators_hotkeys = self.get_valid_validator_hotkeys()
        allocated_hotkeys = self.wandb.get_allocated_hotkeys(validators_hotkeys, True)
        miners_hotkeys = [hotkey for hotkey in miners_hotkeys if hotkey not in allocated_hotkeys]
        # give 5 minutes for every validator to complete the proof of work
        for hotkey in validators_hotkeys:
            await self.exchange_miners_key_auth_exchange(miners_hotkeys, hotkey)
            res = await self.give_validator_pog_access(hotkey)
            if not res:
                bt.logging.error(f"Failed to give validator {hotkey} pog access after 3 attempts")
                # move to the next miner
                continue
            bt.logging.info(f"Successfully gave validator {hotkey} pog access")
            # wait for 5 minutes
            await asyncio.sleep(500)
def get_config():
    """Set up configuration using argparse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=1, help="The chain subnet uid.")
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)
    config = bt.config(parser)
    # Ensure the logging directory exists
    config.full_path = os.path.expanduser( "{}/{}/{}/netuid{}/{}".format( config.logging.logging_dir, config.wallet.name, config.wallet.hotkey, config.netuid, "validator",))
    return config

def main():
    wt = watchtower(get_config())
    while True:
        asyncio.run(wt.pog_orchastractor())
        time.sleep(100)
if __name__ == "__main__":
    main()