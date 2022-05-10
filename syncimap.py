#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" @package docstring
IMAP Sync

Copy emails and folders from an IMAP account to another.
Creates missing folders and skips existing messages (using message-id).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

The code is based on IMAP Copy, author Gabriele Tozzi <gabriele at tozzi.eu> 
https://github.com/gtozzi/imapcp

Also inspired by the code imapsync.pl, http://www.linux-france.org/prj/imapsync/


"""

import imaplib
import sys
import re
import email
import base64,getopt,socket,time,datetime


class main:
	
	NAME = 'syncimap'
	VERSION = '0.4'
		
	def run(self):
		
		config = self.get_config()
		safemode=config['safemode']

		# Parse exclude list
		self.excludes = []
		self.excludes.append(re.compile(config['exclude']))
		self.excluded_folders = []

		self.t0 = time.time()
		self.timestart = self.t0
		
		srcconn = self.connect_and_login('1',config)
		srctype = self.__getServerType(srcconn)
		#print "Source server type is", srctype
		print ("Banner: %s" % srcconn.welcome.decode('utf-8'))
		(typ, data) = srcconn.capability()
		print ("Host1 capability: %s" % data[0].decode('utf-8'))
		
		dstconn = self.connect_and_login('2',config)					
		dsttype = self.__getServerType(dstconn)
		#print "Destination server type is", dsttype
		print ("Banner: %s" % dstconn.welcome.decode('utf-8'))
		(typ, data) = dstconn.capability()
		print ("Host2 capability: %s" % data[0].decode('utf-8'))
		
		totsize=0
		tmess=0
		srcfolders = self.__listMailboxes(srcconn,config['nofoldersizes'])
		
		if len(self.excluded_folders)>0:
			print ("Excluding folders matching pattern '%s': %s" % (config['exclude'],self.excluded_folders))
		
		separator=srcfolders[0]['delimiter']
		print ("Host1 separator: [%s]" %  separator)
							
		dstfolders = self.__listMailboxes(dstconn,config['nofoldersizes'])
		separator=dstfolders[0]['delimiter']
		print ("Host2 separator: [%s]" %  separator)
		
		p='OFF'
		if config['safemode']:	p='ON'
		print ("Safe mode: %s" % p)

		print ("Source mailboxes:")
		print ("++++ Calculating sizes ++++")
		for item in srcfolders:
			if not config['nofoldersizes']:
				totsize += int(item['size'])
				tmess += int(item['messages'])
				print ("Host1 folder %-35s Size: %9s Messages: %5s" % ('['+item['mailbox']+']',item['size'],item['messages']))
			else:
				print ("Host1 folder %-35s" % ('['+item['mailbox']+']'))
			
		print ("Total size: %d" % totsize)
		print ("Total messages: %d" % tmess)
		print ("Time: %.1f s" % self.timenext())

		totsize=0
		tmess=0
		print ("Destination mailboxes:")
		print ("++++ Calculating sizes ++++")
		for item in dstfolders:
			if not config['nofoldersizes']:
				totsize += int(item['size'])
				tmess += int(item['messages'])
				print ("Host2 folder %-35s Size: %9s Messages: %5s" % ('['+item['mailbox']+']',item['size'],item['messages']))
			else:
				print ("Host2 folder %-35s" % ('['+item['mailbox']+']'))
		print ("Total size: %d" % totsize)
		print ("Total messages: %d" % tmess)
		print ("Time: %.1f s" % self.timenext())

		self.msg_skipped = 0
		self.msg_deleted = 0
		self.msg_transferred  = 0
		self.total_bytes_transferred = 0
		self.msg_flags = 0
		
		# Syncing every source folder
		for f in srcfolders:
            
			# Translate folder name
			srcfolder = f['mailbox']
			dstfolder = self.__translateFolderName(srcfolder, srctype, dsttype)
            
			# Check for folder in exclusion list
			'''
			skip = False
			for e in self.excludes:
				if e.match(srcfolder):
					skip = True
					break
			if skip:
				print "Skipping", srcfolder, "(excluded)"
				continue
			'''
			print ("++++ Syncing", srcfolder, 'into', dstfolder)

			# Create dst mailbox when missing
			if not safemode:
				dstconn.create(dstfolder)
            
			# Select source mailbox readonly
			(res, data) = srcconn.select(srcfolder, True)
			if res == 'NO' and srctype == 'exchange' and 'special mailbox' in data[0]:
				print ("Skipping special Microsoft Exchange Mailbox", srcfolder)
				continue
			dstconn.select(dstfolder, False)
            
			# Fetch all destination messages imap IDS
			dstids = self.__listMessages(dstconn,config)
			print ("Found", len(dstids), "messages in destination folder")
            
			# Fetch destination messages ID
			print ("Acquiring message IDs...")
			dstmexids = []
			for did in dstids:
				dstmexids.append(self.__getMessageId(dstconn, did)[0])
			print (len(dstmexids), "message IDs acquired.")

			# Fetch all source messages imap IDS
			srcids = self.__listMessages(srcconn,config)
			
			srcmexids = []
			srcflags = []
			for sid in srcids:
				mid,flags = self.__getMessageId(srcconn, sid)
				srcmexids.append(mid)
				try:
					if config['nosyncflags']:
						pass
				except:
					srcflags.append(flags)
					
			dstdelids = []
			
			for did in dstids:
				mid = self.__getMessageId(dstconn,did)[0]
				if not mid in srcmexids:
					# Message not found, prepare to delete it
					#print "Delete message", mid
					dstdelids.append(did)
					
			#delete unknown dst messages
			print ("Found", len(dstdelids), "messages in destination folder for delete")
			for did in dstdelids:
				if not (safemode) and config['delete2']:
					print ("Delete %s/%s message" % (dstfolder,did))
					self.msg_deleted += 1
					dstconn.store(did,'+FLAGS','\Deleted')
				
			
			
			print ("Found", len(srcids), "messages in source folder")
			# Sync data
			for index, mid in enumerate(srcmexids):			
				if not mid in dstmexids:
					# Message not found, syncing it
					self.msg_transferred += 1
					print ("Copying message", mid)
					mex = self.__getMessage(srcconn, srcids[index])
					if not safemode:
						try:
							flags = srcflags[index]
							dstconn.append(dstfolder, flags, None, mex)
							self.msg_flags += 1
						except:
							dstconn.append(dstfolder, None, None, mex)
				else:
					self.msg_skipped += 1
					print ("Skipping message", mid)
				
			'''
			if config['expunge1']:
				print "Expunging host1 folder %s" % srcfolder
				if not safemode:
					srcconn.expunge()
			'''	
			if config['expunge2']:
				print ("Expunging host2 folder %s" % dstfolder)
				if not safemode:
					dstconn.expunge()
					
				
		print ("++++ End looping on each folder")

		self.timediff = time.time() - self.timestart
		self.stats()

		# Logout
		srcconn.logout()
		dstconn.logout()
	
	def __listMailboxes(self, conn,nofoldersize=True):
		"""
		@param conn: Active IMAP connection
		@return Returns a list of dict{ 'flags', 'delimiter', 'mailbox') }
		"""
		(res, data) = conn.list()
		if res != 'OK':
			raise RuntimeError('Unvalid reply: ' + res)
		list_re = re.compile(r'\((?P<flags>.*)\)\s+"(?P<delimiter>.*)"\s+"?(?P<name>[^"]*)"?')
		folders = []
		for d in data:
			m = list_re.match(d.decode('UTF-8'))
			if not m:
				raise RuntimeError('No match: ' + d.decode('UTF-8'))
			flags, delimiter, mailbox = m.groups()
			for e in self.excludes:
				if e.match(mailbox):
					self.excluded_folders.append(mailbox)
					continue
				else:
					mcount=-1
					msize=-1
					if not nofoldersize:
						mcount,msize = self.getMailboxSize(conn,mailbox)
					folders.append({
						'flags': flags,
						'delimiter': delimiter,
						'mailbox': mailbox,
						'messages': mcount,
						'size': msize
			})
		return folders

	def __listMessages(self, conn, config):
		"""
		List all messages in the given conn and current mailbox.
            
		@returns a list of message imap identifiers
		"""
		#(res, data) = conn.search(None, 'ALL')
		cmd = '(undeleted'
		try:
			if config['maxage']!=None:
				date = (datetime.date.today() - datetime.timedelta(int(config['maxage']))).strftime("%d-%b-%Y")
				cmd += ' SENTSINCE {data}'.format(data=date)
		except:
			pass
		try:
			if config['minage']!=None:
				date = (datetime.date.today() - datetime.timedelta(int(config['minage']))).strftime("%d-%b-%Y")
				cmd += ' SENTBEFORE {data}'.format(data=date)
		except:
			pass
		try:
			if config['maxsize']!=None:
				cmd += ' SMALLER {data}'.format(data=int(config['maxsize']))
		except:
			pass
		'''
		try:
			if config['skipheader']!=None:
				cmd += ' not (HEADER {data})'.format(data=config['skipheader'])
		except:
			pass
		'''	
		cmd += ')'
		#print (cmd)
		try:
				(res, data) = conn.search(None, cmd)
				if res != 'OK':
					raise RuntimeError('Unvalid reply: ' + res)
				msgids = data[0].split()
		except Exception as e:
			msgids = []
			print (" Exception __listMessages: ",str(e))
        
		return msgids

	def __getMessageId(self, conn, imapid):
		"""
		returns "Message-ID"
		"""
		(res, data) = conn.fetch(imapid, '(BODY.PEEK[HEADER] FLAGS)')
		if res != 'OK':
			raise RuntimeError('Unvalid reply: ' + res)
		headers = email.message_from_string(data[0][1].decode('UTF-8'))
		#return headers['Message-ID'],imaplib.ParseFlags(data[1].replace('\Recent',''))
		return headers['Message-ID'],data[1]

	def __getMessage(self, conn, imapid):
		"""
		returns full RFC822 message
		"""
		(res, data) = conn.fetch(imapid, '(RFC822)')
		if res != 'OK':
			raise RuntimeError('Unvalid reply: ' + res)
		return data[0][1]

	def __getServerType(self, conn):
		""" Try to guess IMAP server type
		@return One of: unknown, exchange, dovecot
		"""
		regs = {
			'exchange': re.compile('^.*Microsoft Exchange.*$', re.I),
			#'dovecot': re.compile('^.*imapfront.*$', re.I),
			'dovecot': re.compile('^.*Welcome. Ready to serve.*$', re.I),
		}
		for r in regs.keys():
			if regs[r].match(conn.welcome.decode('UTF-8')):
				return r
		return 'unknown'

	def __translateFolderName(self, name, srcformat, dstformat):
		""" Translates forlder name from src server format do dst server format """
       		
		# 1. Transpose into dovecot format (use DOT as folder separator)
		if srcformat == 'exchange':
			name = name.replace('.', '_').replace('/','.')
		elif srcformat == 'dovecot':
			pass
		else:
			pass
        
		# 2. Transpose into output format
		if dstformat == 'exchange':
			name = name .replace('.', '/').replace('_','.')
		elif dstformat == 'dovecot':
			pass
		else:
			pass
        
		return name
	
	# ------------------------------------------------------------
	
	def getMailboxSize(self,conn,mailbox,pattern=''):
		
		number_of_messages_all = 0
		size_all = 0
		try:
			result, number_of_messages = conn.select(mailbox, readonly=1) 
			number_of_messages_all += int(number_of_messages[0])
		
			size_folder = 0
			#typ, msg = conn.search(None, 'ALL')
			typ,msg = conn.search(None, '(undeleted)')
			m = [int(x) for x in msg[0].split()] 
			m.sort() 
			if m:
				message_set = "%d:%d" % (m[0], m[-1]) 
				result, sizes_response = conn.fetch(message_set, "(UID RFC822.SIZE)") 
				#print mailbox,m,message_set,sizes_response
				#for i in range(m[0],m[-1]): 
				for i in range(len(m)): 
					tmp = sizes_response[i].split() 
					size_folder += int(tmp[-1].replace(')', ''))
			else: 
				size_folder = 0
		
			size_all += size_folder 

		except:
			pass

		return number_of_messages_all,size_all
		
		
	def timenext(self):
		dt = 0
		t1 = time.time();
		dt = t1 - self.t0
		self.t0 = t1
		return(dt)

	
	def decode5t(self,passw):
		for i in range(0,5):
			passw=base64.b64decode(passw[::-1])
		return passw.decode('UTF-8')

	def print_version(self):
		print ("%s version %s" % (self.NAME,self.VERSION))

	def stats(self):
		print ("++++ Statistics")
		print ("Transfer time                : %.1f %s" % (self.timediff,'sec') )
		print ("Messages transferred         : %d" % self.msg_transferred)
		#print   "(could be $nb_msg_skipped_dry_mode without dry mode)" if ($dry)
		#print   
		print ("Messages skipped             : %d" % self.msg_skipped)
		print ("Messages flags recovery      : %d" % self.msg_flags)
		print ("Messages deleted on host2    : %d" % self.msg_deleted)
		print ("Total bytes transferred      : %d" % self.total_bytes_transferred)
		if self.timediff==0:
			self.timediff=1
		print ("Message rate                 : %.1f %s" % (self.msg_transferred / self.timediff,'messages/s'))


	def print_usage(self):
		"""Prints usage, exits"""
		#    
	
		print('''
Usage: syncimap [OPTIONS]

 --host1       <string>    source imap server. Mandatory
 --port1       <int>       port to connect on host1. Default is 143..
 --user1       <string>    user to login on host1.
 --password1   <string>    password for the user1. 
 --passfile1   <string>    password file for the user1. Contains the password.
 --host2       <string>    destination imap server. Mandatory.
 --port2       <int>       port to connect on host2. Default is 143.
 --user2       <string>    user to login on host2.
 --password2   <string>    password for the user2. 
 --passfile2   <string>    password file for the user2. Contains the password.
 --noauthmd5               don't use MD5 authentification.
 --authmech1   <string>    auth mechanism to use with host1:
                           PLAIN, LOGIN, CRAM-MD5 etc. Use UPPERCASE.
 --authmech2   <string>    auth mechanism to use with host2. See --authmech1
 --ssl1                    use an SSL connection on host1.
 --ssl2                    use an SSL connection on host2.
 --include     <regex>     sync folders matching this regular expression
 --include     <regex>     or this one, etc.
                           in case both --include --exclude options are
                           use, include is done before.
 --exclude     <regex>     skips folders matching this regular expression
                           Several folders to avoid:
                           exclude 'fold1|fold2|f3' skips fold1, fold2 and f3.
 --prefix1     <string>    remove prefix to all destination folders 
                           (usually INBOX. for cyrus imap servers)
                           you can use --prefix1 if your source imap server 
                           does not have NAMESPACE capability.
 --prefix2     <string>    add prefix to all destination folders 
                           (usually INBOX. for cyrus imap servers)
                           use --prefix2 if your target imap server does not
                           have NAMESPACE capability.
 --regextrans2 <regex>     Apply the whole regex to each destination folders.
                           When you play with the --regextrans2 option, first
                           add also the safe options --dry --justfolders
                           Then, when happy, remove --dry, remove --justfolders
 --regexmess   <regex>     Apply the whole regex to each message before transfer.
                           Example: 's/000/ /g'  to replace null by space.
 --regexflag   <regex>     Apply the whole regex to each flags list.
                           Example: 's/\"Junk\"//g'  to remove \"Junk\" flag.
 --sep1        <string>    separator in case namespace is not supported.
 --sep2        <string>    idem.
 --delete2                 delete messages on host2 that are not on 
                           host1 server.
 --expunge2                expunge messages on host2.
 --uidexpunge2             uidexpunge messages on the destination imap server
                           that are not on the source server, requires --delete2
 --syncinternaldates       sets the internal dates on host2 same as host1.
                           Turned on by default. Internal date is the date
                           a message arrived on a host (mtime).
 --idatefromheader         sets the internal dates on host2 same as the
                           \"Date: headers.
 --maxsize     <int>       skip messages larger than <int> bytes
 --maxage      <int>       skip messages older than <int> days.
                           final stats (skipped) don't count older messages
                           see also --minage
 --minage      <int>       skip messages newer than <int> days.
                           final stats (skipped) don't count newer messages
                           You can do (+ are the messages selected):
                           past|----maxage+++++++++++++++>now
                           past|+++++++++++++++minage---->now
                           past|----maxage+++++minage---->now (intersection)
                           past|++++minage-----maxage++++>now (union)
 --skipheader  <regex>     Don't take into account header keyword
                           matching <string> ex: --skipheader 'X.*'
 --useheader   <string>    Use this header to compare messages on both sides.
                           Ex: Message-ID or Subject or Date.
 --skipsize                Don't take message size into account to compare
                           messages on both sides. On by default.
                           Use --no-skipsize for using size comparaison.
 --allowsizemismatch       allow RFC822.SIZE != fetched msg size
                           consider also --skipsize to avoid duplicate messages
                           when running syncs more than one time per mailbox
 --nosyncflags             just does not sync flags of messages already transfered
 --safemode                do nothing, just  what would be done.
 --nofoldersizes           Do not calculate the size of each folder in bytes
                           and message counts. Default is to calculate them.
 --debugimap               imap debug mode for host1 and host2.
 --version                 software version.
 --timeout     <int>       imap connect timeout. 
 --help                    this help.

 
 
Example: to synchronise imap account "test1" on "imap.server1"
                    to  imap account "test2" on "imap.server2"
                    with user1 password "secret1",
                    with user2 password "secret2",
                    and exclude source folders, begins with "^Public|^Koncept|^Kalend|^Kontakt",
                    delete messages on the destination imap server that are not on the source server
                    with SSL connect to source imap server

syncimap \\
	--ssl1 --delete2 --expunge2 --exclude "^Public|^Koncept|^Kalend|^Kontakt" \\
	--host1 imap.server1 --user1 test1 --password1 secret1 \\
	--host2 imap.server2 --user2 test2 --password2 secret2 
''')
		
		sys.exit(2)
		
	def process_cline(self):
		"""Uses getopt to process command line, returns (config, warnings, errors)"""
		# read command line
		try:
			short_args = "v:h"
			long_args = ["host1=", "port1=", "user1=", "password1=", "passfile1=", "ssl1", "authmech1=","prefix1=","sep1=","delete1","expunge1",
			"host2=", "port2=", "user2=", "password2=", "passfile2=", "ssl2", "authmech2=","prefix2=","sep2=","delete2","expunge2", "regextrans2=","uidexpunge2",
			"noauthmd5", "include=", "exclude=", "regexmess=","regexflag=","syncinternaldates","idatefromheader","buffersize=",
			"maxsize=","minage=","maxage=","skipheader=","useheader=","skipsize","allowsizemismatch","nosyncflags","safemode","nofoldersizes",
			"justfoldersizes","debugimap1","debugimap2","debugimap","version","timeout=","help"]
			opts, extraargs = getopt.gnu_getopt(sys.argv[1:], short_args, long_args)
		except Exception as e:
			print ('\nError:', e)
			self.print_usage()
				
		warnings = []
		config = {'host2': 'localhost', 'ssl1':True, 'ssl2':False, 'safemode':False, 'timeout':30,'nofoldersizes':False}
		errors = []
		
		# empty command line
		if not len(opts) and not len(extraargs):
			self.print_usage()
			
		# process each command line option, save in config
		for option, value in opts:
			# host1
			if option in ("--host1"):
				config['host1'] = value
			elif option in ("--port1"):
				#warnings.append("Existing mbox files will be overwritten!")
				config["port1"] = value
			elif option in ("--user1"):
				config['user1'] = value
			elif option in ("--password1"):
				config['password1'] = self.decode5t(value)
			elif option in ("--passfile1"):
				config['passfile1'] = value
			elif option in ("--ssl1"):
				config['ssl1'] = True
			elif option in ("--authmech1"):
				config['authmech1'] = value
			elif option in ("--prefix1"):
				config['prefix1'] = value
			elif option in ("--sep1"):
				config['sep1'] = value
			elif option in ("--delete1"):
				config['delete1'] = True
			elif option in ("--expunge1"):
				config['expunge1'] = True
			# host2	
			elif option in ("--host2"):
				config['host2'] = value
			elif option in ("--port2"):
				config["port2"] = value
			elif option in ("--user2"):
				config['user2'] = value
			elif option in ("--password2"):
				config['password2'] = self.decode5t(value)
			elif option in ("--passfile2"):
				config['passfile2'] = value
			elif option in ("--ssl2"):
				config['ssl2'] = True
			elif option in ("--authmech2"):
				config['authmech2'] = value
			elif option in ("--prefix2"):
				config['prefix2'] = value
			elif option in ("--sep2"):
				config['sep2'] = value
			elif option in ("--delete2"):
				config['delete2'] = True
			elif option in ("--expunge2"):
				config['expunge2'] = True
			elif option in ("--regextrans2"):
				config['regextrans2'] = value
			elif option in ("--uidexpunge2"):
				config['uidexpunge2'] = True
			#others			
			elif option in ("--noauthmd5"):
				config['noauthmd5'] = True
			elif option in ("--include"):
				config['include'] = value
			elif option in ("--exclude"):
				config['exclude'] = value
			elif option in ("--regexmess"):
				config['regexmess'] = value
			elif option in ("--regexflag"):
				config['regexflag'] = value
			elif option in ("--syncinternaldates"):
				config['syncinternaldates'] = True
			elif option in ("--idatefromheader"):
				config['idatefromheader'] = True
			elif option in ("--maxsize"):
				config['maxsize'] = value
			elif option in("--minage"):
				config['minage'] = value
			elif option in("--maxage"):
				config['maxage'] = value
			elif option in ("--skipheader"):
				config['skipheader'] = value
			elif option in ("--useheader"):
				config['useheader'] = value
			elif option in ("--skipsize"):
				config['skipsize'] = True
			elif option in ("--allowsizemismatch"):
				config['allowsizemismatch'] = True
			elif option in ("--nosyncflags"):
				config['nosyncflags'] = True
			elif option in ("--safemode"):
				config['safemode'] = True
			elif option in ("--nofoldersizes"):
				config['nofoldersizes'] = True
			elif option in ("--justfoldersizes"):
				config['justfoldersizes'] = True
			elif option in ("--debugimap1"):
				config['debugimap1'] = True
			elif option in ("--debugimap2"):
				config['debugimap2'] = True
			elif option in ("--debugimap"):
				config['debugimap'] = True
			elif option in ("-v","--version"):
				self.print_version()
			elif option in ("--timeout"):
				config['timeout'] = value
			elif option in ("-h","--help"):
				self.print_usage()
			else:
				errors.append("Unknown option: " + option)
 
		# don't ignore extra arguments
		for arg in extraargs:
			errors.append("Unknown argument: " + arg)
		# done processing command line
		return (config, warnings, errors)

	def check_config(self,config, warnings, errors):
		"""Checks the config for consistency, returns (config, warnings, errors)"""
		
		if 'host1' not in config :
			errors.append("No source server specified, use --host1")
		if 'host2' not in config :
			errors.append("No destination server specified, use --host2")
		if 'user1' not in config:
			errors.append("No username specified, use --user1")
		if 'user2' not in config:
			errors.append("No username specified, use --user2")
		if 'port1' in config:
			if len(config['port1']) > 0:
				try:
					port = int(config['port1'])
					if port > 65535 or port < 0:
						raise ValueError
					config['port1'] = port
				except ValueError:
					errors.append("Invalid port1.  Port must be an integer between 0 and 65535.")
		if 'port2' in config:
			if len(config['port2']) > 0:
				try:
					port = int(config['port2'])
					if port > 65535 or port < 0:
						raise ValueError
					config['port2'] = port
				except ValueError:
					errors.append("Invalid port2.  Port must be an integer between 0 and 65535.")
				
		return (config, warnings, errors)


	def get_config(self):
		"""Gets config from command line and console, returns config"""
	
		config, warnings, errors = self.process_cline()
		config, warnings, errors = self.check_config(config, warnings, errors)
		# show warnings
		for warning in warnings:
			print ("WARNING:", warning)
			
		# show errors, exit
		for error in errors:
			print ("ERROR", error)
		if len(errors):
			sys.exit(2)
					
		# prompt for password, if necessary
		if 'password1' not in config:
			config['password1'] = getpass.getpass()
						
		# defaults
		if 'delete2' not in config:
			config['delete2'] = False
		if 'expunge2' not in config:
			config['expunge2'] = False
		
		
		if not 'port1' in config:
			if config['ssl1']:
				config['port1'] = 993
			else:
				config['port1'] = 143
		if not 'port2' in config:
			if config['ssl2']:
				config['port2'] = 993
			else:
				config['port2'] = 143
 
		# done!
		
		return config


	def connect_and_login(self,typ,config):
		try:
			socket.setdefaulttimeout(float(config['timeout']))
			if config['ssl'+typ]:
				print ("Connecting to '%s' TCP port %d, SSL" % (config['host'+typ], config['port'+typ]))
				server = imaplib.IMAP4_SSL(config['host'+typ], config['port'+typ])
			else:
				print ("Connecting to '%s' TCP port %d" % (config['host'+typ], config['port'+typ]))
				server = imaplib.IMAP4(config['host'+typ], config['port'+typ])
				
			server.login(config['user'+typ], config['password'+typ])
			print ("Success login on [%s] with user [%s]" % (config['host'+typ],config['user'+typ]))
		except socket.gaierror as e:
			(err, desc) = e
			print ("ERROR: problem looking up server '%s' (%s %s)" % (config['host'+typ], err, desc))
			sys.exit(3)
		except socket.error as e:
			print ("ERROR: could not connect to '%s' (%s)" % (config['host'+typ], e))
			sys.exit(4)
		except Exception as e:
			print ("ERROR: Host%s, user%s=%s, password%s=****" % (typ,typ,config['user'+typ],typ))
			print (str(e))
			sys.exit(5)
 
		return server



if __name__ == '__main__':
	app = main()
	app.run()
	sys.exit(0)
