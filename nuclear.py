#!/usr/bin/env python3
import libtorrent as lt
import time
import sys
import os
import json
import requests
from datetime import datetime
import binascii
import tempfile
from threading import Thread
import logging

# Configure the logging settings
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Define the log format
)

# Create a logger
logger = logging.getLogger(__name__)

def get_torrent_info(info_hash_hex, ses):
    # Convert hex info hash to bytes
    info_hash = binascii.unhexlify(info_hash_hex)
    
    # Create magnet link from info hash
    magnet_link = f"magnet:?xt=urn:btih:{info_hash_hex}"
    
    # Create a temporary directory for saving files
    temp_dir = tempfile.mkdtemp()
    
    # Add torrent to session
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = temp_dir  # Set the save path
    handle = ses.add_torrent(params)

    # Wait for metadata to be received
    timeout = 55  # seconds
    start_time = time.time()
    
    while not handle.has_metadata():
        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.error('TIMEOUT: ' + str(info_hash_hex)) 
            # Clean up
            ses.remove_torrent(handle)
            try:
                os.rmdir(temp_dir)
            except:
                pass
            return None
        time.sleep(1)
    
    
    # Get torrent info
    torrent_info = handle.get_torrent_info()
    
    # Helper function to safely decode byte-like objects
    def safe_decode(value):
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                return value.decode('utf-8', errors='replace')
        return value
    
    # Gather detailed information
    result = {
        "name": safe_decode(torrent_info.name()),
        "info_hash": info_hash_hex,
        "total_size": torrent_info.total_size(),
        "piece_length": torrent_info.piece_length(),
        "num_pieces": torrent_info.num_pieces(),
        "creator": safe_decode(torrent_info.creator()) if torrent_info.creator() else "Unknown",
        "comment": safe_decode(torrent_info.comment()) if torrent_info.comment() else "None",
        "creation_date": torrent_info.creation_date(),
        "files": [],
        "trackers": [safe_decode(tracker.url) for tracker in torrent_info.trackers()],
    }
    
    # Get file information
    for file_idx in range(torrent_info.num_files()):
        file_entry = torrent_info.files().at(file_idx)

        result["files"].append({
            safe_decode(file_entry.path):file_entry.size
        })
    
    # Get peer information
    peers_info = []
    for peer in handle.get_peer_info():
        peers_info.append({
            "ip": str(peer.ip),  # Convert IP address to string
            "client": safe_decode(peer.client),
            "flags": str(peer.flags),  # Convert flags to string
            "download_rate": peer.down_speed,
            "upload_rate": peer.up_speed,
        })
    result["peers"] = peers_info
    
    # Get status information
    status = handle.status()
    result["status"] = {
        "state": str(status.state),
        "download_rate": status.download_rate,
        "upload_rate": status.upload_rate,
        "num_seeds": status.num_seeds,
        "num_peers": status.num_peers,
        "progress": status.progress,
        "distributed_copies": status.distributed_copies,
    }
    
    # Remove the torrent from the session
    ses.remove_torrent(handle)
    
    # Clean up the temporary directory
    try:
        os.rmdir(temp_dir)
    except:
        pass
    
    return result

def convert_files_sizes_to_fn(files_sizes):
    all_folders = []

    for file in files_sizes:
        for file_name, file_size in file.items():
            if '/' in file_name:
                folder_name = '/'.join(file_name.split('/')[:-1])
                if folder_name not in all_folders:
                    all_folders.append(folder_name)
                file_name = file_name.split('/')[-1]
            all_folders.append(file_name)

    return '\n'.join(all_folders)

def fetch_metadata(torrent_hash, ses):
    logger.info('FETCHING: ' + str(torrent_hash)) 

    url = "http://176.124.218.154:54321/api/check"
    headers = {"Content-Type": "application/json"}
    data = {'hash':torrent_hash}
    response = requests.post(url, data=json.dumps(data), headers=headers)

    checked_hash = response.json()

    if checked_hash['response']:
        logger.warning('EXISTS: ' + str(torrent_hash)) 
        return

    meta = get_torrent_info(torrent_hash, ses)

    if not meta:
        logger.warning('NO META: ' + str(torrent_hash)) 
        return


    # Define the data to send
    data = {
        "name": meta['name'],
        "hash_v1": meta['info_hash'],
        "bytes_length": meta['total_size'],
        "files_sizes": meta['files'],
        "seeds": int(meta['status']['num_seeds']),
        "peers": int(meta['status']['num_peers']),
        "copies": int(meta['status']['distributed_copies']),
        "is_public": True,
        "updated": datetime.now().isoformat(),  # Convert datetime to string for JSON serialization
        "num_files": len(meta['files']),
        "folders_names": convert_files_sizes_to_fn(meta['files'])
    }

    # Send a POST request to the Flask server
    url = "http://176.124.218.154:54321/api/paste"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(data), headers=headers)


    # Print the response from the server

    logger.info(str(torrent_hash) + f' {response.status_code} ' + str(response.json())) 


# Create session
settings = {
    'user_agent': 'scarecrow/7',
    'listen_interfaces': '0.0.0.0:6881-6889',
    'alert_mask': lt.alert.category_t.all_categories,
    # Enable DHT
    'enable_dht': True,
    # Disable other features we don't need
    'enable_lsd': False,
    'enable_upnp': False,
    'enable_natpmp': False
}


# Initialize session
ses = lt.session(settings)

# Wait for DHT to bootstrap
logger.info("DHT bootstrap...")

# Dictionary to store discovered torrents
discovered_torrents = {}
fetched = []


while True:
    # Process alerts
    alerts = ses.pop_alerts()
    for a in alerts:

        # We're interested in DHT announcements and also capture get_peers requests
        if isinstance(a, lt.dht_announce_alert) or isinstance(a, lt.dht_get_peers_alert): 
            info_hash = str(a.info_hash)
            if info_hash not in fetched:
                if info_hash not in discovered_torrents:
                    discovered_torrents[info_hash] = set()
                if not isinstance(a, lt.dht_get_peers_alert):
                    discovered_torrents[info_hash].add(str(a.ip))
                    logger.debug('[+] peers: ' + str(len(discovered_torrents[info_hash])) + ' ip: ' + str(a.ip) + ' hash: ' + str(info_hash))
                else:
                    logger.debug('[*] peers: ' + str(len(discovered_torrents[info_hash])) + ' hash: ' + str(info_hash))
            else:
                logger.info('[-] ' + str(info_hash))

            
        
    # fetch metadata from torrents with peers > 1

    for torrent_hash, torrent_peers in discovered_torrents.items():
        if len(torrent_peers) > 0 and torrent_hash not in fetched:
        #if torrent_hash not in fetched:
            fetched.append(torrent_hash)

            Thread(target=fetch_metadata, args=(torrent_hash,ses,)).start()


    time.sleep(1)

