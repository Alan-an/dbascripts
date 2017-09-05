##################################################################################################
#  Name:        Oracle.py                                                                        #
#  Author:      Randy Johnson                                                                    #
#  Description: This is a Python library for Oracle. It is an attempt to create a library for    #
#               functions that are common to many DBA scripts.                                   #
#  Functions:   ChunkString(InStr, Len)                                                          #
#               CheckPythonVersion()                                                             #
#               ConvertSize(bytes)                                                               #
#               DumpConfig(ConfigFile)                                                           #
#               ErrorCheck(Stdout, ComponentList=['ALL_COMPONENTS'])                             #
#               FormatNumber(s, tSep=',', dSep='.')                                              #
#               GetAsmHome(Oratab='/etc/oratab')                                                 #
#               GetClustername()                                                                 #
#               GetDbState()                                                                     #
#               GetNodes()                                                                       #
#               GetOracleVersion()                                                               #
#               GetParameter(Parameter)                                                          #
#               GetPassword(Name, User, Decrypt, PasswdFilename='/home/oracle/dba/etc/.passwd')  #
#               GetRedologInfo()                                                                 #
#               GetRmanConfig(ConnectString='target /')                                          #
#               GetVips()                                                                        #
#               IsExecutable(Filepath)                                                           #
#               IsReadable(Filepath)                                                             #
#               LoadFacilities(FacilitiesFile)                                                   #
#               LoadOratab(Oratab='')                                                            #
#               LookupError(Error)                                                               #
#               Olsnodes(Parm='')                                                                #
#               ParseConnectString(InStr)                                                        #
#               ParseSqlout(Sqlout, Sqlkey, Colsep)                                              #
#               PrintError(Sql, Stdout, ErrorList=[])                                            #
#               ProcessConfig(ConfigFile, Section)                                               #
#               RunDgmgrl(DgbCmd, ErrChk=True, ConnectString='/')                                #
#               RunRman(RCV, ErrChk=True, ConnectString='target /')                              #
#               RunSqlplus(Sql, ErrChk=False, ConnectString='/ as sysdba')                       #
#               SetOracleEnv(Sid, Oratab='/etc/oratab')                                          #
#               TnsCheck(TnsName)                                                                #
#               ValidateDate(DateStr)                                                            #
#               WriteFile(Filename, Text, Append=False)                                          #
#                                                                                                #
# History:                                                                                       #
#                                                                                                #
# Date       Ver. Who              Change Description                                            #
# ---------- ---- ---------------- ------------------------------------------------------------- #
# 04/06/2012 1.00 Randy Johnson    Initial release.                                              #
# 04/24/2012 1.10 Randy Johnson    Fixed bug caused when LD_LIBRARY_PATH is not set.             #
# 07/10/2014 1.20 Randy Johnson    Added a ton of settings and column formatting to RunSqlplus.  #
# 02/16/2015 1.30 Randy Johnson    Removed ... from the sqlplus SET Header                       #
#                                  Added the IsExecutable() function for testing files.          #
#                                  Heavily modified the GetDbState() function.                   #
#                                  Renamed the formatStackTrace() function to PythonStackTrace() #
# 03/07/2015 2.00 Randy Johnson    Updated print statements for Python 3.4 compatibility.        #
# 07/31/2015 2.10 Randy Johnson    Added ParstConnectString() function to allow network connect. #
#                                  Added import getpass.getpass()                                #
# 08/04/2015 2.20 Randy Johnson    Added import of strptime.                                     #
# 08/04/2015 2.30 Randy Johnson    Modified the SetOracleEnv() function. Now returns null for    #
#                                  OracleSid and OracleHome if ORACLE_SID not found in the       #
#                                  /etc/oratab file.                                             #
# 08/14/2015 2.31 Randy Johnson    Added the -L option to RunSqlplus() so it only tries to logon #
#                                  1 time.                                                       #
# 08/23/2015 2.32 Randy Johnson    Minor changes.                                                #
# 09/04/2015 2.33 Randy Johnson    Changed GetNodes to return {} in event of failure. Formerly   #
#                                  returned ''.                                                  #
# 11/07/2015 2.34 Randy Johnson    Added GetRmanConfig()                                         #
#                                  changed:  Popen([Rman, 'target ', '/'], ...                   #
#                                  to:       Popen([Rman, ConnectString],                        #
# 11/20/2015 2.35 Randy Johnson    PythonStackTrace() repaced with traceback.format_exc()        #
# 01/05/2016 2.36 Randy Johnson    Added base64 and pickle to the imports when Python verison is #
#                                  >= 3.                                                         #
# 07/12/2016 2.37 Randy Johnson    Added GetOracleVersion()                                      #
# 07/12/2017 2.38 Randy Johnson    Replaced Stdout.strip() with Stdout.rstrip() in RunSqlplus.   #
# 08/22/2017 2.39 Randy Johnson    ErrorCheck()                                                  #
#                                  changed: MatchObj = search(Facility + '-[0-9]+', line)        #
#                                       to: MatchObj = search(Facility + '-\d\d\d\d', line)      #
#                                  Added ResultSet class.                                        #
# 09/05/2017 2.40 Randy Johnson    updated the LoadOratab() function to reduce code and improve  #
#                                  efficiency.                                                   #
#                                                                                                #
##################################################################################################

# --------------------------------------
# ---- Import Python Modules -----------
# --------------------------------------
import traceback

from datetime     import datetime
from getpass      import getpass
from math         import floor
from math         import log
from math         import pow
from subprocess   import PIPE
from subprocess   import Popen
from subprocess   import STDOUT
from os           import environ
from os           import access
from os           import path
from os           import walk
from os           import getpgid
from os           import unlink
from os           import getpgid
from os           import unlink
from os           import W_OK as WriteOk
from os           import R_OK as ReadOk
from os           import X_OK as ExecOk
from os.path      import basename
from os.path      import isfile
from os.path      import join as pathjoin
from re           import match
from re           import search
from re           import IGNORECASE
from re           import compile
from sys          import exit
from sys          import exc_info
from sys          import stdout as termout
from sys          import version_info
from signal       import SIGPIPE
from signal       import SIG_DFL
from signal       import signal
from time         import strptime
from time         import sleep


# ------------------------------------------------
# Imports that are conditional on Python Version.
# ------------------------------------------------
if (version_info[0] >= 3):
  import pickle
  from configparser import SafeConfigParser
  from base64       import b64decode
else:
  import cPickle as pickle
  from ConfigParser import SafeConfigParser
# ------------------------------------------------

# For handling termination in stdout pipe; ex: when you run: oerrdump | head
signal(SIGPIPE, SIG_DFL)


# Set min/max compatible Python versions.
# ----------------------------------------
PyMaxVer = 3.4
PyMinVer = 2.4

# -------------------------------------------------
# ---- Function and Class Definitions ------------
# -------------------------------------------------
# ---------------------------------------------------------------------------
# Clas: ResultSet()
# Desc: Runs a query in sqlplus
# ---------------------------------------------------------------------------
class ResultSet:
  def __init__(self, sel):
    self.table = []
    self.row_count = 0
    self.errors = []
    self.rc = 0
    self.stdout = ''
    colsep = '~'
    Sql  = "set pagesize      0\n"
    Sql += "set heading     off\n"
    Sql += "set lines     32767\n"
    Sql += "set feedback    off\n"
    Sql += "set echo        off\n"
    Sql += "set colsep      '" + colsep + "'\n"
    Sql += "\n"
    Sql += sel + ';'

    (self.rc, self.stdout, self.errors) = RunSqlplus(Sql, True, ConnectString = "/ as sysdba")
    if (self.rc == 0):
      for row in self.stdout.split('\n'):
        columns = map(str.strip,row.split(colsep))
        self.table.append(columns)
      self.row_count = len(self.table)
    else:
      self.table.append([])
      self.row_count = 0

  def print_table(self):
    for row in self.table:
      print(row)

  def get_table(self):
      return self.table

  def get_row_count(self):
    return self.row_count

  def get_errors(self):
    return self.errors

  def get_sqlout(self):
    return self.stdout

  def get_resultcode(self):
    return self.rc
# ---------------------------------------------------------------------------
# End ResultSet()
# ---------------------------------------------------------------------------
  
# ---------------------------------------------------------------------------
# Def : GetOracleVersion()
# Desc: Determines the version of the Oracle binaries.
# Args: <none>
# Retn: 0 or exit(1)
# ---------------------------------------------------------------------------
def GetOracleVersion(OracleHome):

  Sqlplus = pathjoin(OracleHome, 'bin', 'sqlplus')


  # Start Sqlplus and login
  Proc = Popen([Sqlplus, '-v'], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)

  # Fetch the output
  Stdout, SqlErr = Proc.communicate()
  Stdout = Stdout.strip()

  MatchObj = search(r'[0-9][0-9].[0-9].[0-9].[0-9].[0-9]', Stdout)
  if (MatchObj):
    OracleVersion = MatchObj.group()
  else:
    OracleVersion = 'unknown'

  return(OracleVersion)
# ---------------------------------------------------------------------------
# End GetOracleVersion()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : ChunkString()
# Desc: This function returns Cgen (a generator), using a generator
#       comprehension. The generator returns the string sliced, from 0 + a
#       multiple of the length of the chunks, to the length of the chunks + a
#       multiple of the length of the chunks.
#
#       You can iterate over the generator like a list, tuple or string -
#          for i in ChunkString(s,n): ,
#       or convert it into a list (for instance) with list(generator).
#       Generators are more memory efficient than lists because they generator
#       their elements as they are needed, not all at once, however they lack
#       certain features like indexing.
# Args: 1=String value
#     : 2=Length of chunks to return.
# Retn:
# ---------------------------------------------------------------------------
def ChunkString(InStr, Len):
  return((InStr[i:i+Len] for i in range(0, len(InStr), Len)))
# ---------------------------------------------------------------------------
# End ChunkString()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetRedologInfo()
# Desc: Collects information about online redologs.
# Args: None.
# Retn: RedologDict{Group}...
# ---------------------------------------------------------------------------
def GetRedologInfo():
  RedologDict   = {}
  ErrChk        = True
  Colsep        = '~'
  Sqlkey        = 'ONLINE_REDOLOG'
  Match         = compile(r'^' + Sqlkey + '.*')

  Sql  = "set pages 0\n"
  Sql += "  SELECT 'ONLINE_REDOLOG'                                || '" + Colsep + "' ||\n"
  Sql += "         lg.group#                                       || '" + Colsep + "' ||\n"
  Sql += "         lg.thread#                                      || '" + Colsep + "' ||\n"
  Sql += "         lg.sequence#                                    || '" + Colsep + "' ||\n"
  Sql += "         lg.bytes                                        || '" + Colsep + "' ||\n"
  Sql += "         lg.blocksize                                    || '" + Colsep + "' ||\n"
  Sql += "         lg.members                                      || '" + Colsep + "' ||\n"
  Sql += "         lg.archived                                     || '" + Colsep + "' ||\n"
  Sql += "         lg.status                                       || '" + Colsep + "' ||\n"
  Sql += "         lg.first_change#                                || '" + Colsep + "' ||\n"
  Sql += "         lg.next_change#                                 || '" + Colsep + "' ||\n"
  Sql += "         to_char(lg.first_time, 'yyyy-mm-dd hh24:mi:ss') || '" + Colsep + "' ||\n"
  Sql += "         to_char(lg.next_time,  'yyyy-mm-dd hh24:mi:ss')\n"
  Sql += "    FROM v$log lg\n"
  Sql += "ORDER BY lg.group#;"

  # Call RunSqlplus
  # ----------------
  (rc,Stdout,ErrorList) = RunSqlplus(Sql, ErrChk)
  Stdout = Stdout.strip()

  if (rc !=0):
    print('Failure in call to sqlplus.')
    PrintError(Sql, Stdout, ErrorList)
    exit(rc)

  for line in Stdout.split('\n'):
    if (Match.search(line)):
      r = line.split(Colsep)
      Group = int(r[1])
      RedologDict[Group] = {
       'thread'                : int(r[2]),
       'sequence'              : int(r[3]),
       'bytes'                 : int(r[4]),
       'blocksize'             : int(r[5]),
       'members'               : int(r[6]),
       'archived'              : r[7],
       'log_status'            : r[8],
       'first_change_num'      : int(r[9]),
       'next_change_num'       : int(r[10]),
       'first_time'            : r[11],
       'next_time'             : r[12]
      }

  Sql  = "set pages 0\n"
  Sql += "  SELECT 'ONLINE_REDOLOG' || '" + Colsep + "' ||\n"
  Sql += "         lf.group#        || '" + Colsep + "' ||\n"
  Sql += "         lf.member        || '" + Colsep + "' ||\n"
  Sql += "         lf.status        || '" + Colsep + "' ||\n"
  Sql += "         lf.type          || '" + Colsep + "' ||\n"
  Sql += "         lf.is_recovery_dest_file\n"
  Sql += "    FROM v$logfile lf\n"
  Sql += "ORDER BY lf.group#, lf.member;"

  # Call RunSqlplus
  # ----------------
  (rc,Stdout,ErrorList) = RunSqlplus(Sql, ErrChk)
  Stdout = Stdout.strip()

  if (rc !=0):
    print('Failure in call to sqlplus.')
    PrintError(Sql, Stdout, ErrorList)
    exit(rc)

  PrevGroup  = ''
  MemberList = []
  for line in Stdout.split('\n'):
    if (Match.search(line)):
      r = line.split(Colsep)
      Group = int(r[1])
      if(Group == PrevGroup):
        MemberList.append(r[2])
      else:
        MemberList = [r[2]]

      RedologDict[Group]['logfile_status']        = r[3]
      RedologDict[Group]['type']                  = r[4]
      RedologDict[Group]['is_recovery_dest_file'] = r[5]
      RedologDict[Group]['members']               = MemberList
      PrevGroup = Group

  return(RedologDict)
# ---------------------------------------------------------------------------
# End GetRedologInfo()
# ---------------------------------------------------------------------------


# Def : ConvertSize()
# Desc: Reduces the size of a number from Bytes .. Yeta Bytes
# Args: s    = numeric_string
#       tSep = thousands_separation_character (default is ',')
#       dSep = decimal_separation_character (default is '.')
# Retn: formatted string
#---------------------------------------------------------------------------
def ConvertSize(bytes):
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(floor(log(bytes,1024)))
   p = pow(1024,i)
   s = round(bytes/p,2)

   if (s > 0):
       return '%s %s' % (s,size_name[i])
   else:
       return '0B'
# ---------------------------------------------------------------------------
# End ConvertSize()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Def : ValidateDate()
# Desc: Validates a string as a valid date format.
#       Valid formats inclue:
#         1) YYYY-MM-DD
#         2) YYYY-MM-DD HH24
#         2) YYYY-MM-DD HH24:MI
#         2) YYYY-MM-DD HH24:MI:SS
# Args: String representing a date or datetime.
# Retn: tuple of (True or False, 'D' or DT')
# ---------------------------------------------------------------------------
def ValidateDate(DateStr):
  try:
    #datetime.strptime(DateStr, '%Y-%m-%d')
    strptime(DateStr, '%Y-%m-%d')
    return (True, 'YYYY-MM-DD')
  except ValueError:
    pass

  try:
    #datetime.strptime(DateStr, '%Y-%m-%d %H')
    strptime(DateStr, '%Y-%m-%d %H')
    return (True, 'YYYY-MM-DD HH24')
  except ValueError:
    pass

  try:
    #datetime.strptime(DateStr, '%Y-%m-%d %H:%M')
    strptime(DateStr, '%Y-%m-%d %H:%M')
    return (True, 'YYYY-MM-DD HH24:MI')
  except ValueError:
    pass

  try:
    #datetime.strptime(DateStr, '%Y-%m-%d %H:%M:%S')
    strptime(DateStr, '%Y-%m-%d %H:%M:%S')
    return (True, 'YYYY-MM-DD HH24:MI:SS')
  except ValueError:
    pass

  return (False, '')
# ---------------------------------------------------------------------------
# End ValidateDate()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Def : ParseConnectString()
# Desc: Parses a connect string
#       Expected input strings follow:
#         1) tnsname
#         2) username@tnsname
#         3) username/password
#         4) username@tnsname
#         3) username/password@tnsname.
# Args: string representing a complete/partitial connect string.
# Retn: tuple of Username, Password, TnsName
# ---------------------------------------------------------------------------
def ParseConnectString(InStr):
  TnsName  = ''
  Username = ''
  Password = ''
  ConnStr  = ''

  if ('@' in InStr and '/' in InStr):
    (junk, TnsName)  = InStr.split('@')
    (Username, Password) = junk.split('/')
  else:
    if ('@' not in InStr and '/' not in InStr):
      TnsName = InStr
    else:
      if ('@' in InStr and '/' not in InStr):
        (Username, TnsName) = InStr.split('@')

      if ('/' in InStr and '@' not in InStr):
        (Username, Password) = InStr.split('/')

    if (Username == ''):
      if (version_info[0] >= 3):
        Username = input('\nEnter user name: ')
      else:
        Username = raw_input('\nEnter user name: ')

    if (Password == ''):
      Password = getpass('\nEnter password: ')

    if (Username == '' or Password == '') :
      print('Username and password are required when specifying a connect string.')
      print('Connect string: %s' % InStr)
      exit(1)

   # Formulate the connect string.
  if (TnsName == ''):
    ConnStr = Username + '/' + Password
  else:
    ConnStr = Username + '/' + Password + '@' + TnsName

  if (Username.upper() == 'SYS'):
    ConnStr = ConnStr + ' as sysdba'

  return(ConnStr)
# ---------------------------------------------------------------------------
# End ParseConnectString()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Clas: Logger()
# Desc: Tee's print output to a file.
# ---------------------------------------------------------------------------
class Logger(object):

  def __init__(self,text):
    from sys import stdout
    self.logfile = text
    self.terminal = stdout
    self.log = open(self.logfile, "w")

    if (version_info[0] >= 3):
      self.encoding = stdout.encoding
      self.flush = stdout.flush
      self.errors = stdout.errors

  def write(self, message):
    self.terminal.write(message)
    self.log.write(message)
# ---------------------------------------------------------------------------
# End Logger()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : CheckPythonVersion()
# Desc: Checks the version of Python and prints error and exit(1) if not
#       within required range.
# Args: rv=requried version
# Retn: 0 or exit(1)
# ---------------------------------------------------------------------------
def CheckPythonVersion():
  import sys

  v = float(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))
  if v >= PyMinVer and v <= PyMaxVer:
    return(str(sys.version_info[0]) + '.' + str(sys.version_info[1]) + '.' + str(sys.version_info[2]))
  else:
    print( "\nError: The version of your Python interpreter (%1.1f) must between %1.1f and %1.1f\n" % (v, PyMinVer, PyMaxVer) )
    exit(1)
# ---------------------------------------------------------------------------
# End CheckPythonVersion()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Sub : TnsCheck()
# Desc: Verifies a tnsping lookup
# Args: ORACLE_SID
# Retn: 0 if successful, 1 if TNS Lookup failed (TNS-03505), >1 Other errors
# ----------------------------------------------------------------------------
def TnsCheck(TnsName):
  rc           = 0
  TnsRc        = 0
  TnsOut       = ''
  TnsErr       = ''
  ErrorStack   = []
  Tnsping      = pathjoin(environ['ORACLE_HOME'], 'bin', 'tnsping')

  try:
    proc = Popen([Tnsping, TnsName], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False)
    (Tnsout, TnsErr) = proc.communicate()
  except:
    print('\n%s' % traceback.format_exc())
    print('tnsping failed: %s (check tnsnames.ora file)' %s )
    return(proc.returncode)

  Tnsout = Tnsout.strip()

  ComponentList = ['network']
  (rc, ErrorList) = ErrorCheck(Tnsout, ComponentList)

  if (rc != 0):
    PrintError(Tnsping + " " + TnsName, Tnsout, ErrorList)

  return(rc)
# ---------------------------------------------------------------------------
# End TnsCheck()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : ParseSqlout()
# Desc: Parses sqlplus output and returns a dictionary structure of values.
# Args: Sqlout = stdout from sqlplus
#       Sqlkey = record identifier
#       Colsep = column delimiter.
# Retn: ValueDict{}
# ---------------------------------------------------------------------------
def ParseSqlout(Sqlout, Sqlkey, Colsep):
  ValuesDict = {}
  ValuesList = []
  i          = 0

  Match = compile(r'^' + Sqlkey + '.*')
  for line in Sqlout.split('\n'):
    if (Match.search(line)):
      try:
        ValuesList = line.split(Colsep)[1:]
        i += 1
        ValuesDict[i] = ValuesList
        exit()
      except:
        pass

  return(ValuesDict)
# ---------------------------------------------------------------------------
# End ParseSqlout()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : WriteFile
# Desc: Creates a text file and writes a string to the file.
# Args: Filename, Text (string to write to file)
# Retn: <none>
# ---------------------------------------------------------------------------
def WriteFile(Filename, Text, Append=False):

  try:
    if (Append == True):
      f = open(Filename, 'a')
    else:
      f = open(Filename, 'w')
  except:
    print('Failed to open file for write: %s' % Filename)
    exit(1)

  f.write(Text)
  f.close()
# ---------------------------------------------------------------------------
# End WriteFile()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : DumpConfig()
# Desc: Dumps the configuration file to stdout.
# Args: <none>
# Retn: <none>
# ---------------------------------------------------------------------------
def DumpConfig(ConfigFile):
  Config = SafeConfigParser()

  # Load the configuration file.
  # -----------------------------
  if (IsReadable(ConfigFile)):
    Config.read(ConfigFile)
    ConfigSections = Config.sections()
  else:
    print('\nConfiguration file does not exist or is not readable: %s' % ConfigFile)
    exit(1)

  print('\nConfiguration: %s' % ConfigFile)
  print('-------------------------------------------------------------------')
  print('Sections: %s' % ConfigSections)
  print(ConfigSections)
  for Section in ConfigSections:
    print('\n[%s]' % Section)
    for Option in sorted(Config.options(Section)):
      try:
        Value = Config.get(Section, Option)
      except:
        print('\n%s' % traceback.format_exc())
        print('Error parsing config file. Oracle.py->DumpConfig->ConfigConfig(%s)\n' % ConfigFile)
        exit(1)
      print('%-40s = %-40s' % (Option, Value))
    print
  return
# ---------------------------------------------------------------------------
# End DumpConfig()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : ProcessConfig()
# Desc: Loads a dictionary with key/value pairs from the config file.
# Args: ConfigFile = the name of the configuration file, example: mtk.conf
#       Section = the section of the config file to process, example: [migration]
# Retn: ConfigDict: dictionary structure of key/values from the section
#       specified.
# ---------------------------------------------------------------------------
def ProcessConfig(ConfigFile, Section):
  Config     = SafeConfigParser()
  ConfigDict = {}

  # Load the configuration file.
  # -----------------------------
  if (IsReadable(ConfigFile)):
    Config.read(ConfigFile)
  else:
    print('\nConfiguration file does not exist or is not readable: %s' % ConfigFile)
    exit(1)

  if (not (Section in Config.sections())):
    print('Section not found in configuration file.')
    print('  File    : %s' % ConfigFile)
    print('  Section : %s' % Section)
    print('\nCheck configuration file for [%s] section (case sensitive).' % Section)
    exit(1)

  for Option in sorted(Config.options(Section)):
    try:
      ConfigDict[Option] = Config.get(Section, Option)
    except:
      print('\n%s' % traceback.format_exc())
      print('\nError parsing config file. Oracle.py->ProcessConfig->ConfigConfig(%s)\n' % ConfigFile)
      exit(1)

  return(ConfigDict)
# ---------------------------------------------------------------------------
# End ProcessConfig()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : IsExecutable()
# Desc: Verifies that a file is readable and executable.
# Args: Filepath = Fully qualified filename.
# Retn: 1 file is readable and executable by the current user.
#       0 file failed isfile, read or execute check.
# ---------------------------------------------------------------------------
def IsExecutable(Filepath):
  if (isfile(Filepath) and access(Filepath, ReadOk) and access(Filepath, ExecOk)):
    return True
  else:
    return False
# ---------------------------------------------------------------------------
# End IsExecutable()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : IsReadable()
# Desc: Verifies that a file is readable.
# Args: Filepath = Fully qualified filename.
# Retn: 1 file is readable by the current user.
#       0 file failed isfile or read check.
# ---------------------------------------------------------------------------
def IsReadable(Filepath):
  if (isfile(Filepath) and access(Filepath, ReadOk)):
    return True
  else:
    return False
# ---------------------------------------------------------------------------
# End IsReadable()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetParameter()
# Desc: Calls sqlplus and retrieves 1 parameter value.
# Args: Parameter
# Retn: Parameter value
# ---------------------------------------------------------------------------
def GetParameter(Parameter):
  ErrChk = True
  Sql    = ''
  Value  = ''

  Sql += "column value form a500\n"
  Sql += "set pages 0\n"
  Sql += "set feedback off\n"
  Sql += "set echo off\n\n"
  Sql += "select value\n"
  Sql += "  from ( select sv.ksppstvl  value\n"
  Sql += "           from sys.x$ksppi  i,\n"
  Sql += "                sys.x$ksppsv sv\n"
  Sql += "          where i.indx = sv.indx\n"
  Sql += "            and i.ksppinm = '" + Parameter.lower() + "');"

  # Call RunSqlplus
  # ----------------
  (rc,Stdout,ErrorList) = RunSqlplus(Sql, ErrChk)
  Stdout = Stdout.strip()
  Value = Stdout

  if (rc !=0):
    print('Failure in call to sqlplus.')
    PrintError(Sql, Stdout, ErrorList)
    exit(rc)

  return(Value)
# ---------------------------------------------------------------------------
# End GetParameter()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetRmanConfig()
# Desc: Calls rman and retrieves all configuration settings.
# Args: Connection Strin (optional, defaults to 'target /')
# Retn: Config = a list of configuration settings
# ---------------------------------------------------------------------------
def GetRmanConfig(ConnectString='target /'):
  ErrChk = True
  Rcv    = ''
  Config = []
  Rcv    = 'show all;'

  # Call Rman
  # ----------------
  (rc,Stdout,ErrorList) = RunRman(Rcv, ErrChk, ConnectString)

  # Parse and print the report
  if (Stdout != ''):
    for line in Stdout.split('\n'):
      if (line.find('CONFIGURE ',0, 10) >= 0):
        Config.append(line)

  if (rc !=0):
    print('Failure in call to rman.')
    PrintError(Rcv, Stdout, ErrorList)
    exit(rc)

  return(Config)
# ---------------------------------------------------------------------------
# End GetRmanConfig()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetNodes()
# Desc: Calls olsnodes -n (list node names with node numbers).
# Args: <none>
# Retn: NodeDict[NodeName] : NodeId)
# ---------------------------------------------------------------------------
def GetNodes():
  NodeDict = {}

  # Setup the ASM environment
  # -----------------------------
  AsmHome = GetAsmHome()
  AsmBin = path.join(AsmHome, 'bin')
  Olsnodes = path.join(AsmBin, 'olsnodes')
  if (not IsExecutable(Olsnodes)):
    print('The following command cannot is not executable:', Olsnodes)
    exit(1)

  # Execute olsnodes -n
  try:
    GridProc = Popen([Olsnodes, '-n'], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)
  except:
    print('\n%s' % traceback.format_exc())
    print('Error in call to olsnodes -n')

  rc = GridProc.wait()
  if (rc != 0):
    print(rc, Stdout)
    return({})
  else:
    Stdout = GridProc.stdout.readlines()
    for line in Stdout:
      NodeName = line.split()[0]
      NodeId  = line.split()[1]
      NodeDict[NodeName] = NodeId
    return(NodeDict)
# ---------------------------------------------------------------------------
# End GetNodes()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetVips()
# Desc: Calls olsnodes -i (print virtual IP address with the node name)
# Args: <none>
# Retn: NodeDict[NodeName] : NodeVip)
# ---------------------------------------------------------------------------
def GetVips():
  VipDict = {}

  # Setup the ASM environment
  # -----------------------------
  AsmHome = GetAsmHome()
  AsmBin = path.join(AsmHome, 'bin')
  Olsnodes = path.join(AsmBin, 'olsnodes')
  if (not IsExecutable(Olsnodes)):
    print('The following command cannot is not executable:', Olsnodes)
    exit(1)

  # Execute olsnodes -i
  try:
    GridProc = Popen([Olsnodes, '-i'], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)
  except:
    print('\n%s' % traceback.format_exc())
    print('Error in call to olsnodes -i')

  rc = GridProc.wait()
  if (rc != 0):
    print(rc, Stdout)
    return({})
  else:
    Stdout = GridProc.stdout.readlines()
    for line in Stdout:
      NodeName = line.split()[0]
      NodeVip  = line.split()[1]
      VipDict[NodeName] = NodeVip
    return(VipDict)
# ---------------------------------------------------------------------------
# End GetNodes()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetClustername()
# Desc: Calls olsnodes -c (cluster name)
# Args: <none>
# Retn: Clustername
# ---------------------------------------------------------------------------
def GetClustername():
  Clustername = ''

  # Setup the ASM environment
  # -----------------------------
  AsmHome = GetAsmHome()
  AsmBin = path.join(AsmHome, 'bin')
  Olsnodes = path.join(AsmBin, 'olsnodes')
  if (not IsExecutable(Olsnodes)):
    print('The following command cannot is not executable:', Olsnodes)
    exit(1)

  # Execute olsnodes -c
  try:
    GridProc = Popen([Olsnodes, '-c'], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)
  except:
    print('\n%s' % traceback.format_exc())
    print('Error in call to olsnodes -c')

  rc = GridProc.wait()
  if (rc != 0):
    print(rc, Stdout)
    return('')
  else:
    Clustername = GridProc.stdout.read()
    return(Clustername.strip())
# ---------------------------------------------------------------------------
# End GetClustername()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : Olsnodes()
# Desc: Calls olsnodes and returns stdout.
# Args: <none>
# Retn: stdout
# ---------------------------------------------------------------------------
def Olsnodes(Parm=''):
  NodeDict = {}

  # Setup the ASM environment
  # -----------------------------
  AsmHome = GetAsmHome()
  AsmBin = path.join(AsmHome, 'bin')
  Olsnodes = path.join(AsmBin, 'olsnodes')
  if (not IsExecutable(Olsnodes)):
    print('The following command cannot is not executable:', Olsnodes)
    exit(1)

  if (Parm != ''):
    Parm = '-' + Parm
    try:
      GridProc = Popen([Olsnodes, Parm], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)
    except:
      print('\n%s' % traceback.format_exc())
      print('Error in call to olsnodes -%s' % Parm)
  else:
    try:
      GridProc = Popen([Olsnodes], stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=False, universal_newlines=True, close_fds=True)
    except:
      print('\n%s' % traceback.format_exc())
      print('Error in call to olsnodes')

  rc = GridProc.wait()
  return(rc, Stdout.strip())
# ---------------------------------------------------------------------------
# End GetNodes()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : LoadOratab()
# Desc: Parses the oratab file and returns a dictionary structure of:
#        {'dbm'      : '/u01/app/oracle/product/11.2.0.3/dbhome_1',
#         'biuat'    : '/u01/app/oracle/product/11.2.0.3/dbhome_1',
#         ...
#        }
#       Note** the start/stop flag is parsed but not saved.
#       If the fully qualified oratab file name is passed in it is prepended
#       to a list of standard locations (/etc/oratab, /var/opt/oracle/oratab)
#       This list of oratab locations are then searched in order. The first
#       one to be successfully opened will be used.
# Args: Oratab (optional, defaults to '')
# Retn: OratabDict (dictionary object)
# ---------------------------------------------------------------------------
def LoadOratab(Oratab=''):
  OraSid     = ''
  OraHome    = ''
  OraFlag    = ''
  OratabDict = {}
  OratabList = []
  OratabLoc  = ['/etc/oratab','/var/opt/oracle/oratab']

  # If an oratab file name has been passed in...
  if (Oratab != ''):
    # If the oratab file name passed in is not already in the list of common locations...
    if (not (Oratab in OratabLoc)):
      OratabLoc.insert(0, Oratab)

  for Oratab in OratabLoc:
    if (isfile(Oratab)):
      try:
        otab = open(Oratab)
        break                          # exit the loop if the file can be opened.
      except:
        print('\n%s' % traceback.format_exc())
        print('\nCannot open oratab file: ' + Oratab + ' for read.')
        return {}

  # The following replaces the commented code below (###!)
  if (otab == ''):
    return {}
  else:
    for line in otab.readlines():
      line = line.split('#', 1)[0].strip()
      Count = line.count(':')
      if (Count >= 1):
        OraFlag = ''
        if (Count == 1):
          (OraSid, OraHome) = line.split(':')
        elif (Count == 2):
          (OraSid, OraHome, OraFlag) = line.split(':')
        elif (Count >= 3):
          OraSid = line.split(':')[0]
          OraHome = line.split(':')[1]
          OraFlag = line.split(':')[2]
        OratabDict[OraSid] = OraHome

  ###! OratabContents = otab.read().split('\n')
  ###! for line in OratabContents:
  ###!   pos = line.find('#')
  ###!   if (pos >= 0):                     # Comment character found.
  ###!     line = line[0:pos]
  ###!   line = line.strip()
  ###!   if (line != ''):
  ###!     Count = line.count(':')
  ###!     if (Count == 2):
  ###!       try:
  ###!         (OraSid, OraHome, OraFlag) = line.split(':')
  ###!         OratabDict[OraSid] = OraHome
  ###!       except:
  ###!         pass
  ###!     elif (Count == 1):
  ###!       try:
  ###!         (OraSid, OraHome) = line.split(':')
  ###!         OratabDict[OraSid] = OraHome
  ###!       except:
  ###!         pass
  
  return(OratabDict)
# ---------------------------------------------------------------------------
# End LoadOratab()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : GetAsmHome()
# Desc: Get the Oracle Home directory for ASM
# Args: FQN of the Oratab file (defaults to /etc/oratab)
# Retn: OracleHome = $ASM_HOME
# ---------------------------------------------------------------------------
def GetAsmHome(Oratab='/etc/oratab'):
  AsmHome = ''
  OratabDict = LoadOratab(Oratab)
  AsmMatch = compile(r'^\+ASM.*')
  for OracleSid in sorted(list(OratabDict.keys())):
    if (AsmMatch.search(OracleSid)):
      AsmHome = OratabDict[OracleSid]
  return(AsmHome)
# ---------------------------------------------------------------------------
# End GetAsmHome()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : RunSqlplus()
# Desc: Calls sqlplus and runs a sql script passed in in the Sql parameter.
#       Optionally calls ErrorCheck() to scan for errors then calls PrintError
#       if any are found. The call stack looks like this...
#       CallingRoutine
#          ^    +-----> RunSqlplus()
#          |                +-----> ErrorCheck()
#          |                +-----> PrintError()
#          |                            +-----> LookupError()
#          |                                          |
#          |                +--> if error exit(rc)    |
#          +------------------------------------------+
#
#          1) Calling routing calls RunSqlplus
#                - 1 parameter. SQL to run (string)
#                - Returns Result Set (1 string)
#          2) RunSqlplus calls ErrorCheck
#                - 2 parameters. Stdout (string), and ComponentList (List of components for looking up potential errors)
#                - Returns 2 values. Return code (int), and ErrorStack which is a list of lists ([ErrorString, line]
#          3) RunSqlplus calls PrintError
#                - Only if return code from ErrorCheck != 0 (an error was found)
#                - Calls PrintError with three parameters:
#                    Sql       = the original SQL statement run.
#                    Stdout    = the output generated by the sqlplus session.
#                    ErrorList = the list of error codes and lines containing the errors (see #2 above).
#                - Returns Stdout to calling routine.
#
# Args: Sql, string containing SQL to execute.
#       ErrChk, True/False determines whether or not to check output for errors.
#       ConnectString, used for connecting to the database
# Retn: If ErrChk=True then return:
#          rc (return code, integer, 0=no errors)
#          Output (string, stdout+stderr)
#          ErrorList (list, error stack)
#       If ErrChk=False then return Stdout only
# ---------------------------------------------------------------------------
def RunSqlplus(Sql, ErrChk=False, ConnectString='/ as sysdba'):
  SqlHeader = ''

  #SqlHeader += "-- set truncate after linesize on\n"
  SqlHeader += "btitle                          off\n"
  SqlHeader += "repfooter                       off\n"
  SqlHeader += "repheader                       off\n"
  SqlHeader += "ttitle                          off\n"
  SqlHeader += "set appinfo                     off\n"
  SqlHeader += "set arraysize                   500\n"
  SqlHeader += "set autocommit                  off\n"
  SqlHeader += "set autoprint                   off\n"
  SqlHeader += "set autorecovery                off\n"
  SqlHeader += "set autotrace                   off\n"
  SqlHeader += "set blockterminator             \".\"\n"
  SqlHeader += "set cmdsep                      off\n"
  SqlHeader += "set colsep                      \" \"\n"
  SqlHeader += "set concat                      \".\"\n"
  SqlHeader += "set copycommit                  0\n"
  SqlHeader += "set copytypecheck               on\n"
  SqlHeader += "set define                      \"&\"\n"
  SqlHeader += "set describe                    depth 1 linenum off indent on\n"
  SqlHeader += "set document                    off\n"
  SqlHeader += "set echo                        off\n"
  SqlHeader += "set embedded                    off\n"
  ###!SqlHeader += "set errorlogging                off\n"
  SqlHeader += "set escape                      off\n"
  SqlHeader += "set escchar                     off\n"
  ###!SqlHeader += "set exitcommit                  on\n"
  SqlHeader += "set feedback                    off\n"
  SqlHeader += "set flush                       on\n"
  SqlHeader += "set heading                     on\n"
  SqlHeader += "set headsep                     \"|\"\n"
  SqlHeader += "set linesize                    32767\n"
  SqlHeader += "set loboffset                   1\n"
  SqlHeader += "set logsource                   \"\"\n"
  SqlHeader += "set long                        10000000\n"
  SqlHeader += "set longchunksize               10000000\n"
  SqlHeader += "set markup html                 off \n"
  SqlHeader += "set newpage                     1\n"
  SqlHeader += "set null                        \"\"\n"
  SqlHeader += "set numformat                   \"\"\n"
  SqlHeader += "set numwidth                    15\n"
  SqlHeader += "set pagesize                    50\n"
  SqlHeader += "set pause                       off\n"
  SqlHeader += "set pno                         0\n"
  SqlHeader += "set recsep                      wrap\n"
  SqlHeader += "set recsepchar                  \" \"\n"
  ###!SqlHeader += "set securedcol                  off\n"
  SqlHeader += "set serveroutput                on size unlimited\n"
  SqlHeader += "set shiftinout                  invisible\n"
  SqlHeader += "set showmode                    off\n"
  SqlHeader += "set space                       1\n"
  SqlHeader += "set sqlblanklines               off\n"
  SqlHeader += "set sqlcase                     mixed\n"
  SqlHeader += "set sqlcontinue                 \"> \"\n"
  SqlHeader += "set sqlnumber                   on\n"
  SqlHeader += "set sqlprefix                   \"#\"\n"
  SqlHeader += "set sqlterminator               \";\"\n"
  SqlHeader += "set suffix                      sql\n"
  SqlHeader += "set tab                         off\n"
  SqlHeader += "set termout                     on\n"
  SqlHeader += "set time                        off\n"
  SqlHeader += "set timing                      off\n"
  SqlHeader += "set trimout                     on\n"
  SqlHeader += "set trimspool                   on\n"
  SqlHeader += "set underline                   \"-\"\n"
  SqlHeader += "set verify                      off\n"
  SqlHeader += "set wrap                        on\n"
  SqlHeader += "\n"

  SqlHeader += "column BLOCKS                   format 999,999,999,999\n"
  SqlHeader += "column BYTES                    format 999,999,999,999\n"
  SqlHeader += "column BYTES_CACHED             format 999,999,999,999\n"
  SqlHeader += "column BYTES_COALESCED          format 999,999,999,999\n"
  SqlHeader += "column BYTES_FREE               format 999,999,999,999\n"
  SqlHeader += "column BYTES_USED               format 999,999,999,999\n"
  SqlHeader += "column CLU_COLUMN_NAME          format a40\n"
  SqlHeader += "column CLUSTER_NAME             format a30\n"
  SqlHeader += "column CLUSTER_TYPE             format a10\n"
  SqlHeader += "column COLUMN_NAME              format a40\n"
  SqlHeader += "column COMPATIBILITY            format a15\n"
  SqlHeader += "column CONSTRAINT_NAME          format a30\n"
  SqlHeader += "column DATABASE_COMPATIBILITY   format a15\n"
  SqlHeader += "column DB_LINK                  format a20\n"
  SqlHeader += "column DBNAME                   format a10\n"
  SqlHeader += "column DIRECTORY_NAME           format a30\n"
  SqlHeader += "column DIRECTORY_PATH           format a100\n"
  SqlHeader += "column EXTENTS                  format 999,999\n"
  SqlHeader += "column FILE_NAME                format a50\n"
  SqlHeader += "column FUNCTION_NAME            format a30\n"
  SqlHeader += "column GBYTES                   format 999,999,999\n"
  SqlHeader += "column GRANTEE                  format a15\n"
  SqlHeader += "column GRANTEE_NAME             format a15\n"
  SqlHeader += "column HOST                     format a30\n"
  SqlHeader += "column HOST_NAME                format a30\n"
  SqlHeader += "column INDEX_NAME               format a30\n"
  SqlHeader += "column INDEX_OWNER              format a15\n"
  SqlHeader += "column INDEX_TYPE               format a10\n"
  SqlHeader += "column INSTANCE_NAME            format a10\n"
  SqlHeader += "column IOT_NAME                 format a30\n"
  SqlHeader += "column IOT_TYPE                 format a15\n"
  SqlHeader += "column JOB_MODE                 format a10\n"
  SqlHeader += "column KSPPINM                  format a20\n"
  SqlHeader += "column KSPPSTVL                 format a20\n"
  SqlHeader += "column MASTER_OWNER             format a15\n"
  SqlHeader += "column MBYTES                   format 999,999,999\n"
  SqlHeader += "column MEMBER                   format a60\n"
  SqlHeader += "column MESSAGE                  format a50\n"
  SqlHeader += "column MVIEW_NAME               format a30\n"
  SqlHeader += "column MVIEW_TABLE_OWNER        format a15\n"
  SqlHeader += "column NAME                     format a50\n"
  SqlHeader += "column NUM_ROWS                 format 999,999,999\n"
  SqlHeader += "column OBJECT_NAME              format a30\n"
  SqlHeader += "column OBJECT_OWNER             format a15\n"
  SqlHeader += "column OBJECT_TYPE              format a13\n"
  SqlHeader += "column OPERATION                format a10\n"
  SqlHeader += "column OPNAME                   format a40\n"
  SqlHeader += "column OWNER                    format a15\n"
  SqlHeader += "column OWNER_NAME               format a15\n"
  SqlHeader += "column PARTITION_NAME           format a30\n"
  SqlHeader += "column PARTNAME                 format a30\n"
  SqlHeader += "column PARTTYPE                 format a10\n"
  SqlHeader += "column PATH                     format a40\n"
  SqlHeader += "column R_CONSTRAINT_NAME        format a30\n"
  SqlHeader += "column R_OWNER                  format a15\n"
  SqlHeader += "column SEGMENT_NAME             format a30\n"
  SqlHeader += "column SEGMENT_TYPE             format a10\n"
  SqlHeader += "column SEQUENCE_NAME            format a30\n"
  SqlHeader += "column SEQUENCE_OWNER           format a15\n"
  SqlHeader += "column SNAPNAME                 format a30\n"
  SqlHeader += "column SNAPSHOT                 format a30\n"
  SqlHeader += "column STATE                    format a10\n"
  SqlHeader += "column STATISTIC                format a50\n"
  SqlHeader += "column SYNONYM_NAME             format a30\n"
  SqlHeader += "column TABLE_NAME               format a30\n"
  SqlHeader += "column TABLE_OWNER              format a15\n"
  SqlHeader += "column TABLE_SCHEMA             format a15\n"
  SqlHeader += "column TABLESPACE_NAME          format a30\n"
  SqlHeader += "column TARGET_DESC              format a35\n"
  SqlHeader += "column TRIGGER_NAME             format a30\n"
  SqlHeader += "column TRIGGER_OWNER            format a15\n"
  SqlHeader += "column TYPE_NAME                format a30\n"
  SqlHeader += "column TYPE_OWNER               format a15\n"
  SqlHeader += "column USED_BLOCKS              format 999,999,999,999\n"
  SqlHeader += "column USERNAME                 format a20\n"
  SqlHeader += "column VALUE                    format a30\n"
  SqlHeader += "column VIEW_NAME                format a30\n"
  SqlHeader += "column VIEW_TYPE                format a10\n"

  Sql = SqlHeader + Sql

  # Unset the SQLPATH environment variable.
  if ('SQLPATH' in environ.keys()):
    del environ['SQLPATH']

  if (ConnectString == '/ as sysdba'):
    if (not('ORACLE_SID' in environ.keys())):
      print('ORACLE_SID must be set if connect string is:' + ' \'' + ConnectString + '\'')
      return (1, '', [])
    if (not('ORACLE_HOME' in environ.keys())):
      OracleSid, OracleHome = SetOracleEnv(environ['ORACLE_SID'])

  # Set the location of the ORACLE_HOME. If ORACLE_HOME is not set
  # then we'll use the first one we find in the oratab file.
  if ('ORACLE_HOME' in environ.keys()):
    OracleHome = environ['ORACLE_HOME']
    Sqlplus = OracleHome + '/bin/sqlplus'
  else:
    OratabDict = LoadOratab()
    if (len(Oratab) >= 1):
      SidList = OratabDict.keys()
      OracleSid  = SidLit[0]
      OracleHome = OratabDict[SidList[0]]
      environ['ORACLE_HOME'] = OracleHome
      Sqlplus = OracleHome + '/bin/sqlplus'
    else:
      print('ORACLE_HOME is not set')
      return (1, '', [])

  # Start Sqlplus and login
  Sqlproc = Popen([Sqlplus, '-S', '-L', ConnectString], stdin=PIPE, stdout=PIPE, stderr=STDOUT, \
   shell=False, universal_newlines=True, close_fds=True)

  # Execute the SQL
  Sqlproc.stdin.write(Sql)

  # Fetch the output
  Stdout, SqlErr = Sqlproc.communicate()
  Stdout = Stdout.rstrip()
  ###! Stdout = Stdout.strip()

  # Check for sqlplus errors
  if (ErrChk):
    ###! from Migration import ErrorCheck, LookupError
    # Components are installed applications/components such as sqlplus, import, export, rdbms, network, ...
    # ComponentList contains a list of all components for which the error code will be searched.
    # For example a component of rdbms will result in ORA-nnnnn errors being included in the search.
    # ALL_COMPONENTS is an override in the ErrorCheck function that results in *all* installed components
    # being selected. Searching all component errors is pretty fast so for now we'll just search them all.
    # -------------------------------------------------------------------------------------------------------
    #ComponentList = ['sqlplus','rdbms','network','crs','css','evm','has','oracore','plsql','precomp','racg','srvm','svrmgr']
    #ComponentList = ['ALL_COMPONENTS']
    ComponentList = ['sqlplus','rdbms', 'oracore']

    # Brief explanation of what is returned by ErrorCheck()
    # ------------------------------------------------------
    # rc is the return code (0 is good, anything else is bad). ErrorList is a list of list structures
    # (a 2 dimensional arrray in other languages). Each outer element of the array represents 1 error found
    # Sql output. Each inner element has two parts (2 fields), element[0] is the Oracle error code and
    # element[1] is the full line of text in which the error was found.
    # For example an ErrorList might look like this:
    # [['ORA-00001', 'ORA-00001: unique constraint...'],['ORA-00018', 'ORA-00018, 00000, "maximum number of..."']]
    (rc, ErrorList) = ErrorCheck(Stdout, ComponentList)
    return(rc,Stdout,ErrorList)
  else:
    return(Stdout)
# ---------------------------------------------------------------------------
# End RunSqlplus()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : RunRman()
# Desc: Runs rman commands.
# Args: RCV, string, containing rman commands or run block to execute.
#       ErrChk, True/False determines whether or not to check output for errors.
#       ConnectString, used for connecting to the database
# Retn: If ErrChk=True then return:
#          rc (return code, integer, 0=no errors)
#          Output (string, stdout+stderr)
#          ErrorList (list, error stack)
#       If ErrChk=False then return Stdout only
# ---------------------------------------------------------------------------
def RunRman(RCV, ErrChk=True, ConnectString='target /'):
  if (ConnectString == '/ as sysdba'):
    if (not('ORACLE_SID' in environ.keys())):
      print('ORACLE_SID must be set if connect string is:' + ' \'' + ConnectString + '\'')
      return (1, '', [])
    if (not('ORACLE_HOME' in environ.keys())):
      OracleSid, OracleHome = SetOracleEnv(environ['ORACLE_SID'])

  # Set the location of the ORACLE_HOME. If ORACLE_HOME is not set
  # then we'll use the first one we find in the oratab file.
  if ('ORACLE_HOME' in environ.keys()):
    OracleHome = environ['ORACLE_HOME']
    Rman = OracleHome + '/bin/rman'
  else:
    OratabDict = LoadOratab()
    if (len(OratabDict) >= 1):
      SidList = OratabDict.keys()
      OracleSid  = SidList[0]
      OracleHome = OratabDict[SidList[0]]
      environ['ORACLE_HOME'] = OracleHome
      Rman = OracleHome + '/bin/rman'
    else:
      print('ORACLE_HOME is not set')
      return (1, '', [])

  # Start Rman and login
  proc = Popen([Rman, ConnectString], bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=STDOUT, \
   shell=False, universal_newlines=True, close_fds=True)

  # Execute the Sql and fetch the output -
  # Stderr is just a placeholder. We redirected stderr to stdout as follows 'stderr=STDOUT'.
  (Stdout, Stderr) = proc.communicate(RCV)

  # Check for rman errors
  if (ErrChk):
    ###! from Migration import ErrorCheck, ErrorCheck, LookupError, LoadFacilities
    # Components are installed applications/components such as sqlplus, import, export, rdbms, network, ...
    # ComponentList contains a list of all components for which the error code will be searched.
    # For example a component of rdbms will result in ORA-nnnnn errors being included in the search.
    # ALL_COMPONENTS is an override in the ErrorCheck function that results in *all* installed components
    # being selected. Searching all component errors is pretty fast so for now we'll just search them all.
    # -------------------------------------------------------------------------------------------------------
    #ComponentList = ['sqlplus','rdbms','network','crs','css','evm','has','oracore','plsql','precomp','racg','srvm','svrmgr']
    ComponentList = ['ALL_COMPONENTS']

    # Brief explanation of what is returned by ErrorCheck()
    # ------------------------------------------------------
    # rc is the return code (0 is good, anything else is bad). ErrorList is a list of list structures
    # (a 2 dimensional arrray in other languages). Each outer element of the array represents 1 error found
    # Sql output. Each inner element has two parts (2 fields), element[0] is the Oracle error code and
    # element[1] is the full line of text in which the error was found.
    # For example an ErrorList might look like this:
    # [['ORA-00001', 'ORA-00001: unique constraint...'],['ORA-00018', 'ORA-00018, 00000, "maximum number of..."']]
    (rc, ErrorList) = ErrorCheck(Stdout, ComponentList)
    return(rc,Stdout,ErrorList)
  else:
    return(Stdout)
# ---------------------------------------------------------------------------
# End RunRman()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : ErrorCheck()
# Desc: Check tnsping, sqlplus, crsctl, srvctl output for errors.
# Args: Output(output you want to scan for errors)
# Retn: Returns 0=no errors or 1=error found, and error stack (in list form)
#-------------------------------------------------------------------------
def ErrorCheck(Stdout, ComponentList=['ALL_COMPONENTS']):
  FacilityList = []
  ErrorStack   = []
  rc           = 0

  if ('ORACLE_HOME' in environ.keys()):
    OracleHome = environ['ORACLE_HOME']
    FacilitiesFile = OracleHome + '/lib/facility.lis'
    FacilitiesDD = LoadFacilities(FacilitiesFile)
  else:
    print('ORACLE_HOME is not set')
    return (1, [])


    # Determine what errors to check for....
  for key in sorted(FacilitiesDD.keys()):
    if (ComponentList[0].upper() == 'ALL_COMPONENTS'):
      for Component in ComponentList:
        FacilityList.append(key.upper())
    else:
      for Component in ComponentList:
        if (Component == FacilitiesDD[key]['Component']):
          FacilityList.append(key.upper())

  # Component:
  #  Facility class is major error type such as SP1, SP2, IMP, TNS, ...
  #  Component class is the application such as sqlplus, rdbms, imp, network.
  #  A component can have several error facilities. For example the sqlplus
  #  has 5:
  #    grep sqlplus  /u01/app/oracle/product/11.2.0.3/dbhome_1/lib/facility.lis
  #    cpy:sqlplus:*:
  #    sp1:sqlplus:*:
  #    sp2:sqlplus:*:
  #    sp3:sqlplus:*:
  #    spw:sqlplus:*:
  #
  #  The error SP2-06063 breaks down as Component=sqlplus, Facility=sp2, Error=06063. See below:
  #    SP2-06063 : 06063,0, "When SQL*Plus starts, and after CONNECT commands, the site profile\n"
  #    SP2-06063 : // *Document: NO
  #    SP2-06063 : // *Cause:  Usage message.
  #    SP2-06063 : // *Action:

  for line in Stdout.split('\n'):
    for Facility in FacilityList:
      # Check for warning and error messages
      ###~ MatchObj = search(Facility + '-[0-9]+', line)
      MatchObj = search(Facility + '-\d\d\d\d', line)
      if (MatchObj):
        ErrorString = MatchObj.group()
        rc = 1
        ErrorStack.append([ErrorString, line])

  return(rc, ErrorStack)
# ---------------------------------------------------------------------------
# End ErrorCheck()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : LookupError()
# Desc: Parses the ficiliy file and returns a list of lists (2 dim array)
#       containing:
#         facility:component:rename:description
# Args: Facility file name.
# Retn: FacilitiesDD
# ---------------------------------------------------------------------------
def LookupError(Error):
  MsgList     = []
  HeaderFound = False

  if ('ORACLE_HOME' in environ.keys()):
    OracleHome = environ['ORACLE_HOME']
    FacilitiesFile = OracleHome + '/lib/facility.lis'
    FacilitiesDD = LoadFacilities(FacilitiesFile)
  else:
    print('ORACLE_HOME is not set')
    return (1, [])

  try:
    (Facility,ErrCode) = Error.lower().split('-')
  except:
    print('\nInvalid error code.')
    exit(1)

  if (not Facility in FacilitiesDD.keys()):
    print('\nInvalid facility:', Facility)
    exit(1)
  else:
    MessagesFile = OracleHome + '/' + FacilitiesDD[Facility]['Component'] + '/' + 'mesg' + '/' + Facility + 'us.msg'

  try:
    msgfil = open(MessagesFile, 'r')
  except:
    print('\nCannot open Messages file: ' + MessagesFile + ' for read.')
    exit(1)

  MsgFileContents = msgfil.readlines()

  for line in MsgFileContents:
    # lines I'm looking for look like this "00003, 00000, "INTCTL: error while se..."
    # So just looking for something that starts with a string of digits and contains
    # the error code I'm looking for.
    if (HeaderFound):
        MatchObj = match(r'//,*', line)
        if (MatchObj):
          MsgList.append(line.strip())
        else:
          return(MsgList)
    else:
      MatchObj = match('[0]*' + ErrCode + ',', line)
      if (MatchObj):
          ErrCode = MatchObj.group()
          ErrCode = ErrCode[0:ErrCode.find(',')]
          MsgList.append(line.strip())
          HeaderFound = True

  if (len(MsgList) == 0):
    # If error code could not be found let's trim off leading 0's and try again...
    ErrCode = str(int(ErrCode))
    for line in MsgFileContents:
      if (HeaderFound):
          MatchObj = match(r'//,*', line)
          if (MatchObj):
            MsgList.append(line.strip())
          else:
            return(MsgList)
      else:
        MatchObj = match('[0]*' + ErrCode + ',', line)
        if (MatchObj):
            ErrCode = MatchObj.group()
            ErrCode = ErrCode[0:ErrCode.find(',')]
            MsgList.append(line.strip())
            HeaderFound = True

  if (len(MsgList) == 0):
    print('Error not found  : ' + ErrCode)
    print('Msg file         : ' + MessagesFile)

  return(MsgList)
# ---------------------------------------------------------------------------
# End LookupError()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : PrintError()
# Desc: Print a formatted error message.
# Args: ErrorMsg (the error message to be printed)
# Retn: <none>
# ---------------------------------------------------------------------------
def PrintError(Sql, Stdout, ErrorList=[]):
  print('\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')
  print('%s\n' % Sql)
  print('----')
  print(Stdout)
  print('----')
  print
  for Error in ErrorList:
    OracleError = Error[0]
    ErrorString = Error[1]
    Explanation = LookupError(OracleError)
    if (len(Explanation) > 0):
      print('\nExplanation:')
      print('---------------')
      for line in Explanation:
        print(line)
  print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n')
  return
# ---------------------------------------------------------------------------
# End PrintError()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : LoadFacilities()
# Desc: Parses the ficiliy file and returns a list of lists (2 dim array)
#       containing:
#         facility:component:rename:description
# Args: Facility file name.
# Retn: FacilitiesDD
# ---------------------------------------------------------------------------
def LoadFacilities(FacilitiesFile):
  FacDict = {}
  FacDD   = {}

  try:
    facfil = open(FacilitiesFile, 'r')
  except:
    print('\n%s' % traceback.format_exc())
    print('\nCannot open facilities file: ' + FacilitiesFile + ' for read.')
    exit(1)

  FacFileContents = facfil.read().split('\n')
  for line in FacFileContents:
    if (not (search(r'^\s*$', line))):   # skip blank lines
      if (line.find('#') >= 0):
        line=line[0:line.find('#')]
      if (line.count(':') == 3):   # ignore lines that do not contain 3 :'s
        (Facility, Component, OldName, Description) = line.split(':')
        FacList = [Facility.strip(), Component.strip(), OldName.strip(), Description.strip()]
        if (Facility != ''):
          FacDict = {
           'Component'   : Component.strip(),
           'OldName'     : OldName.strip(),
           'Description' : Description.strip()
          }
          FacDD[Facility.strip()] = FacDict
  return(FacDD)
# ---------------------------------------------------------------------------
# End LoadFacilities()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : SetOracleEnv()
# Desc: Setup your environemnt, eg. ORACLE_HOME, ORACLE_SID. (Parses oratab
#       file).
# Args: Sid = The ORACLE_SID of the home you want to configure for
#       Oratab = FQN of the oratab file (optional)
# Retn: OracleSid = $ORACLE_SID
#       OracleHome = $ORACLE_HOME
# ---------------------------------------------------------------------------
def SetOracleEnv(Sid, Oratab='/etc/oratab'):
  OracleSid = ''
  OracleHome = ''

  OratabDict = LoadOratab()
  SidCount = len(OratabDict.keys())

  if (SidCount > 0):
    if (Sid in OratabDict.keys()):
      OracleSid  = Sid
      OracleHome = OratabDict[OracleSid]
      environ['ORACLE_SID']  = OracleSid
      environ['ORACLE_HOME'] = OracleHome

      if ('LD_LIBRARY_PATH' in environ.keys()):
        if (environ['LD_LIBRARY_PATH'] != ''):
          environ['LD_LIBRARY_PATH'] = OracleHome + '/lib' + ':' + environ['LD_LIBRARY_PATH']       # prepend to LD_LIBRARY_PATH
        else:
          environ['LD_LIBRARY_PATH'] = OracleHome + '/lib'
      else:
        environ['LD_LIBRARY_PATH'] = OracleHome + '/lib'

  return(OracleSid, OracleHome)
# ---------------------------------------------------------------------------
# End SetOracleEnv()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Function: GetPassword()
# Desc    : Retrieve database password from the password file.
# Args    : db_unique_name, database username
# Retn    : If success then returns password. If not return blank.
# ---------------------------------------------------------------------------
def GetPassword(Name, User, Decrypt, PasswdFilename='/home/oracle/dba/etc/.passwd'):

  try:
    PasswdFile = open(PasswdFilename, 'r')
    pwdContents = PasswdFile.read()

  except:
    print('\nCannot open password file for read:', PasswdFilename)

  for pwdLine in pwdContents.split('\n'):
    if (not (match(r'^\s*$', pwdLine))):               # skip blank lines
      if (not (match(r'^\s#\s*$', pwdLine))):          # skip commented lines
        if (pwdLine.count(':') == 2):                  # ignore lines that do not contain 2 colon's (:).
          (pwDbname, pwUser, pwPass) = pwdLine.split(':')
          if ((pwDbname == Name) and (pwUser.upper() == User.upper()) and (pwPass != '')):
            if(Decrypt):
              try:
                if (version_info[0] >= 3):
                  pwPass = b64decode(pwPass.encode('utf-8')).decode('utf-8')
                else:
                  pwPass = pwPass.decode('base64','strict')
              except:
                print("\n  Are you sure the password was properly")
                print("  encoded? Check it with epw and try again.")

            return(pwPass)
  return('')
# ---------------------------------------------------------------------------
# End GetPassword()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Sub : GetDbState()
# Desc: Get the current state of the database (down, mounted, open)
# Args: <none>
# Retn: STOPPED, STARTED, MOUNTED, OPEN, UNKNOWN
# ------------------------------------------------------------------------
def GetDbState():
  Colsep     = '!~!'
  DbState    = 'STOPPED'
  rc         = 0
  ErrorStack = []

  Sql  = "set pagesize 0\n";
  Sql += "select 'DB_STATUS' ||'" + Colsep + "'|| upper(status) from v$instance;";

  Stdout = RunSqlplus(Sql, False)

  DbDown = compile(r'.*ORA-01034.*')
  if (DbDown.search(Stdout)):
    return('STOPPED')
  else:
    # DB_STATUS:!~!STARTED
    Key = compile(r'^.*DB_STATUS' + Colsep + '.*')
    for line in Stdout.split('\n'):
      if (Key.search(line)):
        DbState = line.split(Colsep)[1]
        DbState.strip()
        return(DbState)
  return('UNKNOWN')
# ---------------------------------------------------------------------------
# End GetDbState()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : FormatNumber()
# Desc: Simple function to format numbers with commas to separate thousands.
# Args: s    = numeric_string
#       tSep = thousands_separation_character (default is ',')
#       dSep = decimal_separation_character (default is '.')
# Retn: formatted string
# ---------------------------------------------------------------------------
def FormatNumber(s, tSep=',', dSep='.'):

  # Splits a string or float on thousands. GIGO on general input.
  if s == None:
    return(0)

  if not isinstance(s, str):
    s = str(s)

  cnt=0
  numChars=dSep+'0123456789'
  ls=len(s)

  while cnt < ls and s[cnt] not in numChars:
    cnt += 1

  lhs = s[0:cnt]
  s = s[cnt:]
  if (dSep == ''):
    cnt = -1
  else:
    cnt = s.rfind(dSep)

  if (cnt > 0):
    rhs = dSep + s[cnt+1:]
    s = s[:cnt]
  else:
    rhs = ''

  splt=''
  while s != '':
    splt = s[ -3: ] + tSep + splt
    s = s[ :-3 ]

  return(lhs + splt[ :-1 ] + rhs)
# ---------------------------------------------------------------------------
# End FormatNumber()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Def : RunDgmgrl()
# Desc: Runs drmgrl commands.
# Args: DgbCmd, string containing DGMGRL commands or run.
#       ErrChk, True/False determines whether or not to check output for errors.
#       ConnectString, used for connecting to the database
# Retn: If ErrChk=True then return:
#          rc (return code, integer, 0=no errors)
#          Output (string, stdout+stderr)
#          ErrorList (list, error stack)
#       If ErrChk=False then return Stdout only
# ---------------------------------------------------------------------------
def RunDgmgrl(DgbCmd, ErrChk=True, ConnectString='/'):

  if (ConnectString == '/'):
    if (not('ORACLE_SID' in environ.keys())):
      print('ORACLE_SID must be set if connect string is:' + ' \'' + ConnectString + '\'')
      return (1, '', [])
    if (not('ORACLE_HOME' in environ.keys())):
      OracleSid, OracleHome = SetOracleEnv(environ['ORACLE_SID'])

  # Set the location of the ORACLE_HOME. If ORACLE_HOME is not set
  # then we'll use the first one we find in the oratab file.
  if ('ORACLE_HOME' in environ.keys()):
    OracleHome = environ['ORACLE_HOME']
    Dgmgrl = OracleHome + '/bin/dgmgrl'
  else:
    OratabDict = LoadOratab()
    if (len(OratabDict) >= 1):
      SidList = OratabDict.keys()
      OracleSid  = SidList[0]
      OracleHome = OratabDict[SidList[0]]
      environ['ORACLE_HOME'] = OracleHome
      Dgmgrl = OracleHome + '/bin/dgmgrl'
    else:
      print('ORACLE_HOME is not set')
      return (1, '', [])

  # Start Dgmgrl and login
  proc = Popen([Dgmgrl, '-silent', ConnectString], bufsize=-1, stdin=PIPE, stdout=PIPE, stderr=STDOUT, \
   shell=False, universal_newlines=True, close_fds=True)

  # Execute the Sql and fetch the output -
  # Stderr is just a placeholder. We redirected stderr to stdout as follows 'stderr=STDOUT'.
  (Stdout, Stderr) = proc.communicate(DgbCmd)
  rc = proc.returncode

  if(ErrChk == True):
    return(rc,Stdout)
  else:
    return(Stdout)

  ###! # Check for dgmgrl errors
  ###! if (ErrChk):
  ###!   ###! from Migration import ErrorCheck, ErrorCheck, LookupError, LoadFacilities
  ###!   # Components are installed applications/components such as sqlplus, import, export, rdbms, network, ...
  ###!   # ComponentList contains a list of all components for which the error code will be searched.
  ###!   # For example a component of rdbms will result in ORA-nnnnn errors being included in the search.
  ###!   # ALL_COMPONENTS is an override in the ErrorCheck function that results in *all* installed components
  ###!   # being selected. Searching all component errors is pretty fast so for now we'll just search them all.
  ###!   # -------------------------------------------------------------------------------------------------------
  ###!   #ComponentList = ['sqlplus','rdbms','network','crs','css','evm','has','oracore','plsql','precomp','racg','srvm','svrmgr']
  ###!   ComponentList = ['ALL_COMPONENTS']
  ###!
  ###!   # Brief explanation of what is returned by ErrorCheck()
  ###!   # ------------------------------------------------------
  ###!   # rc is the return code (0 is good, anything else is bad). ErrorList is a list of list structures
  ###!   # (a 2 dimensional arrray in other languages). Each outer element of the array represents 1 error found
  ###!   # Sql output. Each inner element has two parts (2 fields), element[0] is the Oracle error code and
  ###!   # element[1] is the full line of text in which the error was found.
  ###!   # For example an ErrorList might look like this:
  ###!   # [['ORA-00001', 'ORA-00001: unique constraint...'],['ORA-00018', 'ORA-00018, 00000, "maximum number of..."']]
  ###!   (rc, ErrorList) = ErrorCheck(Stdout, ComponentList)
  ###!   print(rc)
  ###!   exit()
  ###!   return(rc,Stdout,ErrorList)
  ###! else:
  ###!   return(Stdout)
# ---------------------------------------------------------------------------
# End RunDgmgrl()
# ---------------------------------------------------------------------------


