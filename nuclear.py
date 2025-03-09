#!/usr/bin/env python3
_O='application/json'
_N='Content-Type'
_M=' \t hash: '
_L='[+] \t peers: '
_K='distributed_copies'
_J='num_peers'
_I='num_seeds'
_H='total_size'
_G='info_hash'
_F='0.0.0.0:6881'
_E='listen_interfaces'
_D='name'
_C=False
_B='status'
_A='files'
import libtorrent as lt,time,sys,os,json,requests
from datetime import datetime
import binascii,tempfile
settings={'user_agent':'python_dht_crawler/libreseed/1.3',_E:_F,'alert_mask':lt.alert.category_t.all_categories,'enable_dht':True,'enable_lsd':_C,'enable_upnp':_C,'enable_natpmp':_C}
def get_torrent_info(info_hash_hex):
	N='upload_rate';M='download_rate';G=info_hash_hex;T=binascii.unhexlify(G);H=lt.session({_E:_F});O=f"magnet:?xt=urn:btih:{G}";I=tempfile.mkdtemp();J=lt.parse_magnet_uri(O);J.save_path=I;C=H.add_torrent(J);print('Fetching torrent metadata...');P=22;Q=time.time()
	while not C.has_metadata():
		R=time.time()-Q
		if R>P:
			print('Timeout: Failed to retrieve metadata');H.remove_torrent(C)
			try:os.rmdir(I)
			except:pass
			return
		time.sleep(1)
	print('Metadata received!');A=C.get_torrent_info()
	def D(value):
		B='utf-8';A=value
		if isinstance(A,bytes):
			try:return A.decode(B)
			except UnicodeDecodeError:return A.decode(B,errors='replace')
		return A
	F={_D:D(A.name()),_G:G,_H:A.total_size(),'piece_length':A.piece_length(),'num_pieces':A.num_pieces(),'creator':D(A.creator())if A.creator()else'Unknown','comment':D(A.comment())if A.comment()else'None','creation_date':A.creation_date(),_A:[],'trackers':[D(A.url)for A in A.trackers()]}
	for S in range(A.num_files()):K=A.files().at(S);'\n        result["files"].append({\n            "path": safe_decode(file_entry.path),\n            "size": file_entry.size,\n        })\n        ';F[_A].append({D(K.path):K.size})
	L=[]
	for E in C.get_peer_info():L.append({'ip':str(E.ip),'client':D(E.client),'flags':str(E.flags),M:E.down_speed,N:E.up_speed})
	F['peers']=L;B=C.status();F[_B]={'state':str(B.state),M:B.download_rate,N:B.upload_rate,_I:B.num_seeds,_J:B.num_peers,'progress':B.progress,_K:B.distributed_copies};H.remove_torrent(C)
	try:os.rmdir(I)
	except:pass
	return F
ses=lt.session(settings)
print('Waiting for DHT to bootstrap...')
time.sleep(10)
discovered_torrents={}
fetched=[]
while True:
	alerts=ses.pop_alerts()
	for a in alerts:
		if isinstance(a,lt.dht_announce_alert)or isinstance(a,lt.dht_get_peers_alert):
			info_hash=str(a.info_hash)
			if info_hash not in fetched:
				if info_hash not in discovered_torrents:discovered_torrents[info_hash]=set()
				if not isinstance(a,lt.dht_get_peers_alert):discovered_torrents[info_hash].add(str(a.ip));print(_L+str(len(discovered_torrents[info_hash]))+' \t ip: '+str(a.ip)+_M+str(info_hash))
				else:print(_L+str(len(discovered_torrents[info_hash]))+_M+str(info_hash))
			else:print('[-] \t '+str(info_hash))
	for(torrent_hash,torrent_peers)in discovered_torrents.items():
		if len(torrent_peers)>0 and torrent_hash not in fetched:
			fetched.append(torrent_hash);url='http://176.124.218.154:54321/api/check';headers={_N:_O};data={'hash':torrent_hash};response=requests.post(url,data=json.dumps(data),headers=headers);checked_hash=response.json()
			if checked_hash['response']:print('exists. next');continue
			print('retrieving metadata from hash: '+str(torrent_hash));meta=get_torrent_info(torrent_hash)
			if not meta:continue
			print('sending to database...');files_sizes=[{'file1':512},{'file2':512}];data={_D:meta[_D],'hash_v1':meta[_G],'bytes_length':meta[_H],'files_sizes':meta[_A],'seeds':int(meta[_B][_I]),'peers':int(meta[_B][_J]),'copies':int(meta[_B][_K]),'is_public':True,'updated':datetime.now().isoformat(),'num_files':len(meta[_A])};url='http://176.124.218.154:54321/api/paste';headers={_N:_O};response=requests.post(url,data=json.dumps(data),headers=headers);print(response.status_code);print(response.json())