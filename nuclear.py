#!/usr/bin/env python3
_I='distributed_copies'
_H='num_peers'
_G='num_seeds'
_F='total_size'
_E='info_hash'
_D=False
_C='name'
_B='status'
_A='files'
import libtorrent as lt,time,sys,os,json,requests
from datetime import datetime
import binascii,tempfile
from threading import Thread
import logging
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger=logging.getLogger(__name__)
def get_torrent_info(info_hash_hex,ses):
	N='upload_rate';M='download_rate';H=ses;F=info_hash_hex;T=binascii.unhexlify(F);O=f"magnet:?xt=urn:btih:{F}";I=tempfile.mkdtemp();J=lt.parse_magnet_uri(O);J.save_path=I;C=H.add_torrent(J);P=55;Q=time.time()
	while not C.has_metadata():
		R=time.time()-Q
		if R>P:
			logger.error('TIMEOUT: '+str(F));H.remove_torrent(C)
			try:os.rmdir(I)
			except:pass
			return
		time.sleep(1)
	A=C.get_torrent_info()
	def D(value):
		B='utf-8';A=value
		if isinstance(A,bytes):
			try:return A.decode(B)
			except UnicodeDecodeError:return A.decode(B,errors='replace')
		return A
	G={_C:D(A.name()),_E:F,_F:A.total_size(),'piece_length':A.piece_length(),'num_pieces':A.num_pieces(),'creator':D(A.creator())if A.creator()else'Unknown','comment':D(A.comment())if A.comment()else'None','creation_date':A.creation_date(),_A:[],'trackers':[D(A.url)for A in A.trackers()]}
	for S in range(A.num_files()):K=A.files().at(S);G[_A].append({D(K.path):K.size})
	L=[]
	for E in C.get_peer_info():L.append({'ip':str(E.ip),'client':D(E.client),'flags':str(E.flags),M:E.down_speed,N:E.up_speed})
	G['peers']=L;B=C.status();G[_B]={'state':str(B.state),M:B.download_rate,N:B.upload_rate,_G:B.num_seeds,_H:B.num_peers,'progress':B.progress,_I:B.distributed_copies};H.remove_torrent(C)
	try:os.rmdir(I)
	except:pass
	return G
def convert_files_sizes_to_fn(files_sizes):
	C='/';B=[]
	for E in files_sizes:
		for(A,F)in E.items():
			if C in A:
				D=C.join(A.split(C)[:-1])
				if D not in B:B.append(D)
				A=A.split(C)[-1]
			B.append(A)
	return'\n'.join(B)
def fetch_metadata(torrent_hash,ses):
	H='application/json';G='Content-Type';B=torrent_hash;logger.info('FETCHING: '+str(B));D='https://torrent.libreseed.icu/api/check?test1';E={G:H};F={'hash':B};C=requests.post(D,data=json.dumps(F),headers=E);I=C.json()
	if I['response']:logger.warning('EXISTS: '+str(B));return
	A=get_torrent_info(B,ses)
	if not A:logger.warning('NO META: '+str(B));return
	F={_C:A[_C],'hash_v1':A[_E],'bytes_length':A[_F],'files_sizes':A[_A],'seeds':int(A[_B][_G]),'peers':int(A[_B][_H]),'copies':int(A[_B][_I]),'is_public':True,'updated':datetime.now().isoformat(),'num_files':len(A[_A]),'folders_names':convert_files_sizes_to_fn(A[_A])};D='https://torrent.libreseed.icu/api/paste';E={G:H};C=requests.post(D,data=json.dumps(F),headers=E);logger.info(str(B)+f" {C.status_code} "+str(C.json()))
settings={'user_agent':'libreseed/3.3','listen_interfaces':'0.0.0.0:6881-6889','alert_mask':lt.alert.category_t.all_categories,'enable_dht':True,'enable_lsd':_D,'enable_upnp':_D,'enable_natpmp':_D}
ses=lt.session(settings)
logger.info('DHT bootstrap...')
discovered_torrents={}
fetched=[]
"\nwhile True:\n    fetch_metadata('60a33c6720d6445bdc4e68b0b2b5e48f96dfc39c',ses)\n    fetch_metadata('56bbfd878f4e65d03602ba1ed7cef292c3540f0a',ses)\n    fetch_metadata('ff546b06402409c826ab6a596ae250752d38249b',ses)\n    fetch_metadata('ab345fc81f7d62aebde4c8a1f983a6967e6806c6',ses)\n\n    print('cycle')\n    time.sleep(5)\n\ninput('main')\n"
while True:
	alerts=ses.pop_alerts()
	for a in alerts:
		if isinstance(a,lt.dht_announce_alert)or isinstance(a,lt.dht_get_peers_alert):
			info_hash=str(a.info_hash)
			if info_hash not in fetched:
				if info_hash not in discovered_torrents:discovered_torrents[info_hash]=set()
				if not isinstance(a,lt.dht_get_peers_alert):discovered_torrents[info_hash].add(str(a.ip));logger.info('[+] peers: '+str(len(discovered_torrents[info_hash]))+' ip: '+str(a.ip)+' hash: '+str(info_hash))
				else:0
			else:0
	for(torrent_hash,torrent_peers)in discovered_torrents.items():
		if len(torrent_peers)>0 and torrent_hash not in fetched:fetched.append(torrent_hash);Thread(target=fetch_metadata,args=(torrent_hash,ses)).start()
	time.sleep(1)
