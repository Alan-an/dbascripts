#!/bin/env python

##################################################################################################
#  Name:        fs                                                                               #
#  Author:      Randy Johnson                                                                    #
#  Description: This script can be used to locate statements in the shared pool and              #
#               determine whether they have been executed via Smart Scans.                       #
#                                                                                                #
#               It is based on the observation that the IO_CELL_OFFLOAD_ELIGIBLE_BYTES           #
#               column in V$SQL is only greater than 0 when a statement is executed              #
#               using a Smart Scan. The IO_SAVED_% column attempts to show the ratio of          #
#               of data received from the storage cells to the actual amount of data             #
#               that would have had to be retrieved on non-Exadata storage. Note that            #
#               as of 11.2.0.2, there are issues calculating this value with some queries.       #
#                                                                                                #
#               Note that the AVG_ETIME will not be acurate for parallel queries. The            #
#               ELAPSED_TIME column contains the sum of all parallel slaves. So the              #
#               script divides the value by the number of PX slaves used which gives an          #
#               approximation.                                                                   #
#                                                                                                #
#               Note also that if parallel slaves are spread across multiple nodes on            #
#               a RAC database the PX_SERVERS_EXECUTIONS column will not be set.                 #
#                                                                                                #
#               Credit to Kerry Osborne for the core logic in the SQL queries.                   #
#                                                                                                #
#  Usage: fs [options]                                                                           #
#                                                                                                #
#  Options:                                                                                      #
#    -h, --help    show this help message and exit                                               #
#    -a            search the AWR (default is v$sql)                                             #
#    -b BEGINTIME  begin_interval_time >= BeginTime (default 1960-01-01 00:00:00)                #
#    -e ENDTIME    end_interval_time <= EndTime     (default 2015-08-01 16:37:52)                #
#    -g            search gv$sql (default is v$sql)                                              #
#    -r ROWS       limit output to nnn rows (default 0=off)                                      #
#    -s            print SQL query.                                                              #
#    -i SQLID      value for sql_id                                                              #
#    -t SQLTEXT    value for sql_text                                                            #
#    -v            print version info.                                                           #
#    -x            report Exadata IO reduction.                                                  #
#                                                                                                #
# Todo's                                                                                         #
# Switch from gv$sqltext and v$sqltext (sql_text) to gv$sql and v$sql (sql_fulltext)             #
#                                                                                                #
# History:                                                                                       #
#                                                                                                #
# Date       Ver. Who              Change Description                                            #
# ---------- ---- ---------------- ------------------------------------------------------------- #
# 07/23/2015 1.00 Randy Johnson    Initial write.                                                #
# 07/17/2015 2.00 Randy Johnson    Updated for Python 2.4-3.4 compatibility. Folded in the fsx   #
#                                  script and assigned it to the -x option. Folded in the fs_awr #
#                                  and fsx_awr scripts -a and -a -x options.                     #
# 07/17/2015 2.10 Randy Johnson    Added prompts for username, password, tnsname.                #
#                                  Changed -b and -e options from SnapID to SnapTime.            #
##################################################################################################

# --------------------------------------
# ---- Import Python Modules -----------
# --------------------------------------
from datetime     import datetime
from optparse     import OptionParser
from os           import environ
from os.path      import basename
from signal       import SIG_DFL
from signal       import SIGPIPE
from signal       import signal
from sys          import argv
from sys          import exit
from sys          import version_info
from Oracle       import ParseConnectString
from Oracle       import RunSqlplus
from Oracle       import SetOracleEnv
from Oracle       import ValidateDate


# --------------------------------------
# ---- Main Program --------------------
# --------------------------------------
if (__name__ == '__main__'):
  Cmd            = basename(argv[0]).split('.')[0]
  CmdDesc        = 'Find SQL'
  Version        = '2.10'
  VersionDate    = 'Tue Sep 15 21:02:11 CDT 2015'
  DevState       = 'Production'
  Banner         = CmdDesc + ': Release ' + Version + ' '  + DevState + '. Last updated: ' + VersionDate
  Sql            = ''
  SqlHeader      = '/***** ' + CmdDesc.upper() + ' *****/'
  ErrChk         = False
  ArgParser      = OptionParser()
  Now            = datetime.now()
  EndTime        = (Now.strftime('%Y-%m-%d %H:%M:%S'))
  ConnStr        = ''

  # For handling termination in stdout pipe; ex: when you run: oerrdump | head
  signal(SIGPIPE, SIG_DFL)

  ArgParser.add_option('-a',  dest='Awr',       action='store_true', default=False,                           help="search the AWR (default is v$sql)")
  ArgParser.add_option('-b',  dest='BeginTime',                      default='1960-01-01 00:00:00', type=str, help="begin_interval_time >= BeginTime (default 1960-01-01 00:00:00)")
  ArgParser.add_option('-e',  dest='EndTime',                        default=EndTime,               type=str, help="end_interval_time <= EndTime     (default " + EndTime + ")")
  ArgParser.add_option('-g',  dest='Global',    action='store_true', default=False,                           help="search gv$sql (default is v$sql)")
  ArgParser.add_option('-r',  dest='Rows',                           default=0,                     type=int, help="limit output to nnn rows (default 0=off)")
  ArgParser.add_option('-i',  dest='SqlId',                          default='',                    type=str, help="value for sql_id")
  ArgParser.add_option('-t',  dest='SqlText',                        default='',                    type=str, help="value for sql_text")
  ArgParser.add_option('-x',  dest='ExaOpt',    action='store_true', default=False,                           help="report Exadata IO reduction.")
  ArgParser.add_option('--s', dest='Show',      action='store_true', default=False,                           help="print SQL query.")
  ArgParser.add_option('--v', dest='ShowVer',   action='store_true', default=False,                           help="print version info.")

  # Parse command line arguments
  Options, args = ArgParser.parse_args()

  Awr         = Options.Awr
  BeginTime   = Options.BeginTime
  EndTime     = Options.EndTime
  Global      = Options.Global
  Rows        = str(Options.Rows)
  Show        = Options.Show
  SqlId       = Options.SqlId
  SqlText     = Options.SqlText
  ShowVer     = Options.ShowVer
  ExaOpt      = Options.ExaOpt

  if (ShowVer == True):
    print('\n%s' % Banner)
    exit()

  if (Awr == True and Global == True):
    print("\nAWR option (-a) and Global option (-g) may not be used together.")
    exit(1)

  (ValidDate, BeginTimeFormat) = ValidateDate(BeginTime)
  if (ValidDate == False):
    print("Invalid format for BeginTime. Acceptable formats follow:")
    print("  YYYY-MM-DD")
    print("  YYYY-MM-DD HH24")
    print("  YYYY-MM-DD HH24:MI")
    print("  YYYY-MM-DD HH24:MI:SS")
    exit(1)

  (ValidDate, EndTimeFormat) = ValidateDate(EndTime)
  if (ValidDate == False):
    print("Invalid format for EndTime. Acceptable formats follow:")
    print("  YYYY-MM-DD")
    print("  YYYY-MM-DD HH24")
    print("  YYYY-MM-DD HH24:MI")
    print("  YYYY-MM-DD HH24:MI:SS")
    exit(1)

  if (Awr == True):
    if (ExaOpt == True):
      Sql += "column sql_id               format a14                  heading 'SQL ID'\n"
      Sql += "column plan_hash_value      format 99999999999          heading 'Plan Hash'\n"
      Sql += "column execs                format 9,999,999,999        heading 'Executions'\n"
      Sql += "column avg_etime            format 999,999,999.999      heading 'Avg Ela Sec'\n"
      Sql += "column avg_lio              format 999,999,999,999      heading 'Avg LIO'\n"
      Sql += "column avg_pio              format 999,999,999,999      heading 'Avg PIO'\n"
      Sql += "column rows_proc            format 999,999,999,999      heading 'Rows'\n"
      Sql += "column offloaded            format a3                   heading 'SS'\n"
      Sql += "column pct_offloaded        format 999.99               heading 'SS%'\n"
      Sql += "column sql_text             format a69                  heading 'SQL Text' word_wrap\n"
      Sql += "\n"
      Sql += "  SELECT " + SqlHeader + "\n"
      Sql += "         sql_id\n"
      Sql += "       , plan_hash_value\n"
      Sql += "       , execs\n"
      Sql += "       , avg_etime\n"
      Sql += "       , avg_pio\n"
      Sql += "       , avg_lio\n"
      Sql += "       , rows_proc\n"
      Sql += "       , DECODE(offload_eligible_bytes,0,'No','Yes') offloaded\n"
      ###! Sql += "       , offload_eligible_bytes\n"
      ###! Sql += "       , total_bytes\n"
      Sql += "       , pct_offloaded\n"
      #Sql += "       , io_reduction\n"
      Sql += "       , sql_text\n"
      Sql += "    FROM (SELECT dbms_lob.substr(sql_text,3999,1) sql_text\n"
      Sql += "               , b.*\n"
      Sql += "            FROM dba_hist_sqltext a\n"
      Sql += "               , (    SELECT sql_id\n"
      Sql += "                           , plan_hash_value\n"
      Sql += "                           , SUM(execs) execs\n"
      Sql += "                           , SUM(etime) etime\n"
      Sql += "                           , SUM(etime)/DECODE(SUM(execs),0,1,SUM(execs)) avg_etime\n"
      Sql += "                           , SUM(pio)  /DECODE(SUM(execs),0,1,SUM(execs)) avg_pio\n"
      Sql += "                           , SUM(lio)  /DECODE(SUM(execs),0,1,SUM(execs)) avg_lio\n"
      Sql += "                           , SUM(rows_proc) rows_proc\n"
      Sql += "                           , SUM(offload_eligible_bytes) offload_eligible_bytes\n"
      Sql += "                           , SUM(total_bytes) total_bytes\n"
      Sql += "                           , DECODE(SUM(offload_eligible_bytes),0,0,100 * (SUM(offload_eligible_bytes) / (SUM(total_bytes)))) pct_offloaded\n"
      ###! Sql += "                         , DECODE(SUM(offload_eligible_bytes),0,0,100 * (SUM(offload_eligible_bytes) - (SUM(total_bytes) / DECODE(SUM(offload_eligible_bytes),0,1,(SUM(offload_eligible_bytes)))))) pct_offloaded\n"
      Sql += "                        FROM (SELECT plan_hash_value\n"
      Sql += "                                   , ss.snap_id\n"
      Sql += "                                   , ss.instance_number inst\n"
      Sql += "                                   , begin_interval_time\n"
      Sql += "                                   , sql_id\n"
      Sql += "                                   , IO_OFFLOAD_ELIG_BYTES_DELTA offload_eligible_bytes\n"
      Sql += "                                   , IO_INTERCONNECT_BYTES_DELTA total_bytes\n"
      Sql += "                                   , NVL(executions_delta,0) execs\n"
      Sql += "                                   , elapsed_time_delta /1000000 etime\n"
      Sql += "                                   , (elapsed_time_delta/DECODE(NVL(executions_delta,0),0,1,executions_delta))/1000000 avg_etime\n"
      Sql += "                                   , buffer_gets_delta lio\n"
      Sql += "                                   , disk_reads_delta pio\n"
      Sql += "                                   , rows_processed_delta rows_proc\n"
      Sql += "                                   , (buffer_gets_delta   /DECODE(NVL(executions_delta,0),0,1,executions_delta)) avg_lio\n"
      Sql += "                                   , (rows_processed_delta/DECODE(NVL(executions_delta,0),0,1,executions_delta)) avg_rows\n"
      Sql += "                                   , (disk_reads_delta    /DECODE(NVL(executions_delta,0),0,1,executions_delta)) avg_pio\n"
      Sql += "                                FROM DBA_HIST_SQLSTAT S\n"
      Sql += "                                   , DBA_HIST_SNAPSHOT SS\n"
      Sql += "                               WHERE ss.snap_id         = S.snap_id\n"
      Sql += "                                 AND ss.instance_number = S.instance_number\n"
      ###!Sql += "                                 AND ss.snap_id BETWEEN " + BegSnapId + " AND " + EndSnapId + "\n"
      Sql += "                                 AND ss.begin_interval_time >= TO_DATE('" + BeginTime + "', '" + BeginTimeFormat + "')\n"
      Sql += "                                 AND ss.end_interval_time   <= TO_DATE('" + EndTime   + "', '" + EndTimeFormat   + "')\n"
      Sql += "                              -- AND executions_delta > 0\n"
      Sql += "                             )\n"
      Sql += "                    GROUP BY sql_id\n"
      Sql += "                           , plan_hash_value\n"
      Sql += "                    ORDER BY 5 DESC\n"
      Sql += "                 ) b\n"
      Sql += "           WHERE a.sql_id = b.sql_id\n"
      Sql += "         )\n"
      Sql += "   WHERE sql_text NOT LIKE '%" + SqlHeader + "%'\n"
      if (SqlText != ''):
        Sql += "     AND UPPER(sql_text) LIKE UPPER('%" + SqlText + "%\')\n"
      if (SqlId != ''):
        Sql += "     AND sql_id LIKE '%" + SqlId + "%'\n"
      if (Rows != '0'):
        Sql += "     AND rownum <= " + Rows + "\n";
      Sql += "ORDER BY etime DESC;\n"
    else:
      Sql += "column sql_id               format a14                  heading 'SQL ID'\n"
      Sql += "column plan_hash_value      format 99999999999          heading 'Plan Hash'\n"
      Sql += "column execs                format 9,999,999,999        heading 'Executions'\n"
      Sql += "column avg_etime            format 999,999,999.999      heading 'Avg Ela Sec'\n"
      Sql += "column first_load_time      format a16                  heading 'First Active'\n"
      Sql += "column last_active          format a16                  heading 'Last Active'\n"
      Sql += "column avg_lio              format 999,999,999,999      heading 'Avg LIO's'\n"
      Sql += "column avg_pio              format 999,999,999,999      heading 'Avg PIO's'\n"
      Sql += "column rows_proc            format 999,999,999,999      heading 'Rows Processed'\n"
      Sql += "column sql_text             format a81                  heading 'SQL Text' word_wrap\n"
      Sql += "\n"
      Sql += "  SELECT " + SqlHeader + "\n"
      Sql += "         sql_id\n"
      Sql += "       , plan_hash_value\n"
      Sql += "       , TO_NUMBER(execs) execs\n"
      Sql += "       , avg_etime\n"
      Sql += "       , avg_lio\n"
      Sql += "       , avg_pio\n"
      Sql += "       , rows_proc\n"
      Sql += "       , sql_text\n"
      Sql += "    FROM (SELECT dbms_lob.substr(sql_text,3999,1) sql_text\n"
      Sql += "               , b.*\n"
      Sql += "            FROM dba_hist_sqltext a\n"
      Sql += "               , (   SELECT sql_id\n"
      Sql += "                          , plan_hash_value\n"
      Sql += "                          , SUM(execs) execs\n"
      Sql += "                          , SUM(etime) etime\n"
      Sql += "                          , SUM(etime) / DECODE(SUM(execs),0,1,SUM(execs)) avg_etime\n"
      Sql += "                          , SUM(pio)   / DECODE(SUM(execs),0,1,SUM(execs)) avg_pio\n"
      Sql += "                          , SUM(lio)   / DECODE(SUM(execs),0,1,SUM(execs)) avg_lio\n"
      Sql += "                          , SUM(rows_proc) rows_proc\n"
      Sql += "                       FROM (SELECT plan_hash_value\n"
      Sql += "                                  , ss.snap_id\n"
      Sql += "                                  , ss.instance_number node\n"
      Sql += "                                  , begin_interval_time\n"
      Sql += "                                  , sql_id\n"
      Sql += "                                  , NVL(executions_delta,0) execs\n"
      Sql += "                                  , elapsed_time_delta /1000000 etime\n"
      Sql += "                                  , (elapsed_time_delta/DECODE(NVL(executions_delta,0),0,1,executions_delta))/1000000 avg_etime\n"
      Sql += "                                  , buffer_gets_delta lio\n"
      Sql += "                                  , rows_processed_delta rows_proc\n"
      Sql += "                                  , disk_reads_delta pio\n"
      Sql += "                                  , (buffer_gets_delta   /DECODE(NVL(executions_delta,0),0,1,executions_delta)) avg_lio\n"
      Sql += "                                  , (disk_reads_delta    /DECODE(NVL(executions_delta,0),0,1,executions_delta)) avg_pio\n"
      Sql += "                               FROM dba_hist_sqlstat s\n"
      Sql += "                                  , dba_hist_snapshot ss\n"
      Sql += "                              WHERE ss.snap_id = s.snap_id\n"
      Sql += "                                AND ss.instance_number = s.instance_number\n"
      ###!Sql += "                                AND ss.snap_id BETWEEN " + BegSnapId + " AND " + EndSnapId + "\n"
      Sql += "                                AND ss.begin_interval_time >= TO_DATE('" + BeginTime + "', '" + BeginTimeFormat + "')\n"
      Sql += "                                AND ss.end_interval_time   <= TO_DATE('" + EndTime   + "', '" + EndTimeFormat   + "')\n"
      Sql += "                                -- AND executions_delta > 0\n"
      Sql += "                            )\n"
      Sql += "                   GROUP BY sql_id\n"
      Sql += "                          , plan_hash_value\n"
      Sql += "                   ORDER BY 5 DESC\n"
      Sql += "                 ) b\n"
      Sql += "           WHERE a.sql_id = b.sql_id\n"
      Sql += "         )\n"
      Sql += "   WHERE sql_text NOT LIKE '%" + SqlHeader + "%'\n"
      if (Rows != '0'):
        Sql += "     AND rownum <= " + Rows + "\n";
      if (SqlText != ''):
        Sql += "     AND UPPER(sql_text)     LIKE UPPER('%" + SqlText + "%\')\n"
      if (SqlId != ''):
        Sql += "      AND sql_id LIKE '%" + SqlId + "%'\n"
      Sql += "ORDER BY etime DESC;\n"
  else:
    if (ExaOpt == True):
      if (Global):
        Sql += "column inst                 format 999                  heading 'Inst'\n"
      Sql += "column sql_id               format a14                  heading 'SQL ID'\n"
      Sql += "column sql_text             format a82                  heading 'SQL Text' word_wrap\n"
      Sql += "column plan_hash            format 9999999999           heading 'Plan Hash'\n"
      Sql += "column child                format 9999                 heading 'Child'\n"
      Sql += "column execs                format 9,999,999,999        heading 'Executions'\n"
      #Sql += "column first_load_time      format a16                  heading 'First Active'\n"
      Sql += "column last_active          format a16                  heading 'Last Active'\n"
      Sql += "column avg_px               format 9,999,999,999        heading 'Avg PX'\n"
      Sql += "column offloaded            format a3                   heading 'SS'\n"
      Sql += "column avg_etime            format 999,999,999.999      heading 'Avg Ela Sec'\n"
      Sql += "column pct_io_saved         format 99.99                heading 'IO Saved'\n"
      Sql += "\n"
      Sql += "   SELECT " + SqlHeader + "\n"
      if (Global):
        Sql += "          inst_id inst\n"
        Sql += "        , sql_id\n"
      else:
        Sql += "          sql_id\n"
      Sql += "        , child_number child\n"
      Sql += "        , plan_hash_value plan_hash\n"
      Sql += "        , executions execs\n"
      Sql += "        , (elapsed_time/1000000) / DECODE(NVL(executions,0),0,1,executions)\n"
      Sql += "           / DECODE(px_servers_executions,0,1,px_servers_executions\n"
      Sql += "           / DECODE(NVL(executions,0),0,1,executions)) avg_etime\n"
      #Sql += "        , TO_CHAR(TO_DATE(first_load_time, 'YYYY-MM-DD/HH24:MI:SS'), 'YYYY-MM-DD HH24:MI') first_load_time\n"
      Sql += "        , TO_CHAR(last_active_time,\'yyyy-mm-dd hh24:mi\') last_active\n"
      Sql += "        , px_servers_executions / DECODE(NVL(executions,0),0,1,executions) avg_px\n"
      Sql += "        , DECODE(io_cell_offload_eligible_bytes,0,\'No\',\'Yes\') offloaded\n"
      Sql += "        , DECODE(io_cell_offload_eligible_bytes,0,0,100 *\n"
      Sql += "           (io_cell_offload_eligible_bytes - io_interconnect_bytes) /\n"
      Sql += "           DECODE(io_cell_offload_eligible_bytes,0,1,io_cell_offload_eligible_bytes)) pct_io_saved\n"
      Sql += "        , sql_text\n"
      if (Global):
        Sql += "     FROM gv$sql s\n"
      else:
        Sql += "     FROM v$sql s\n"
      Sql += "    WHERE sql_text NOT LIKE '%" + SqlHeader + "%'\n"
      if (SqlText != ''):
        Sql += "      AND UPPER(sql_text) LIKE UPPER('%" + SqlText + "%\')\n"
      if (SqlId != ''):
        Sql += "      AND sql_id LIKE '%" + SqlId + "%'\n"
      if (Rows != '0'):
        Sql += "      AND rownum <= " + Rows + "\n";
      if (Global):
        Sql += " ORDER BY inst_id\n"
        Sql += "        , sql_id\n"
        Sql += "        , child_number\n"
        Sql += "        , plan_hash_value;\n"
      else:
        Sql += " ORDER BY sql_id\n"
        Sql += "        , child_number\n"
        Sql += "        , plan_hash_value;\n"
    else:
      if (Global):
        Sql += "column inst                 format 999                  heading 'Inst'\n"
      Sql += "column sql_id               format a14                  heading 'SQL ID'\n"
      Sql += "column sql_text             format a94                  heading 'SQL Text' word_wrap\n"
      Sql += "column child                format 9999                 heading 'Child'\n"
      Sql += "column execs                format 9,999,999,999        heading 'Executions'\n"
      #Sql += "column first_load_time      format a16                  heading 'First Active'\n"
      Sql += "column last_active          format a16                  heading 'Last Active'\n"
      Sql += "column plan_hash            format 9999999999           heading 'Plan Hash'\n"
      Sql += "column avg_lio              format 999,999,999,999      heading 'Avg LIO's'\n"
      Sql += "\n"
      Sql += "   SELECT " + SqlHeader + "\n"
      if (Global):
        Sql += "          inst_id inst\n"
        Sql += "        , sql_id\n"
      else:
        Sql += "          sql_id\n"
      Sql += "        , child_number child\n"
      Sql += "        , plan_hash_value plan_hash\n"
      Sql += "        , executions execs\n"
      Sql += "        , (elapsed_time/1000000)/decode(nvl(executions,0),0,1,executions) avg_etime\n"
      #Sql += "          TO_CHAR(TO_DATE(first_load_time, 'YYYY-MM-DD/HH24:MI:SS'), 'YYYY-MM-DD HH24:MI') first_load_time,\n"
      Sql += "        , TO_CHAR(last_active_time,\'yyyy-mm-dd hh24:mi\') last_active\n"
      Sql += "        , buffer_gets/decode(nvl(executions,0),0,1,executions) avg_lio\n"
      Sql += "        , sql_text\n"
      if (Global):
        Sql += "     FROM gv$sql s\n"
      else:
        Sql += "     FROM v$sql s\n"
      Sql += "    WHERE sql_text NOT LIKE '%" + SqlHeader + "%'\n"
      if (SqlText != ''):
        Sql += "      AND UPPER(sql_text) LIKE UPPER('%" + SqlText + "%\')\n"
      if (SqlId != ''):
        Sql += "      AND sql_id LIKE '%" + SqlId + "%'\n"
      if (Rows != '0'):
        Sql += "      AND rownum <= " + Rows + "\n";
      if (Global):
        Sql += " ORDER BY inst_id\n"
        Sql += "        , sql_id\n"
        Sql += "        , child_number\n"
        Sql += "        , plan_hash_value;\n"
      else:
        Sql += " ORDER BY sql_id\n"
        Sql += "        , child_number\n"
        Sql += "        , plan_hash_value;\n"

  Sql = Sql.strip()

  if(Show):
    print('-----------cut-----------cut-----------cut-----------cut-----------cut-----------')
    print(Sql)
    print('-----------cut-----------cut-----------cut-----------cut-----------cut-----------')
    exit()

  # Check/setup the Oracle environment
  if (not('ORACLE_SID' in list(environ.keys()))):
    print('ORACLE_SID is required.')
    exit(1)
  else:
    # Set the ORACLE_HOME just in case it isn't set already.
    if (not('ORACLE_HOME' in list(environ.keys()))):
      (OracleSid, OracleHome) = SetOracleEnv(environ['ORACLE_SID'])

  # Parse the connect string if any, prompt for username, password if needed.
  if (len(args) > 0 and Show == False):
    InStr = args[0]
    ConnStr = ParseConnectString(InStr)

  # Execute the report
  if (ConnStr != ''):
    (Stdout) = RunSqlplus(Sql, ErrChk, ConnStr)
  else:
    (Stdout) = RunSqlplus(Sql, ErrChk)

  # Print the report
  if (Stdout != ''):
    print('\n%s' % Stdout)

  exit(0)
# --------------------------------------
# ---- End Main Program ----------------
# --------------------------------------
