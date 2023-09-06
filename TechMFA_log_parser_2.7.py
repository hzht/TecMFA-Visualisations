# HZH
# Version: 2.7
# Date: 2023-01-30

"""
A line graph showing for each individual device, X axis being instances, Y axis being time in seconds (graph: individual host): 
    1 line with different colours, 2 dots at the end specifying averages.
    INSTANCES of online and offline logins in DEVICE's LOG – end to end
    Online login (average time of all instances) - dot at the end of the chart
    OFFLINE login (average time of all instances) - dot at the end of the chart

A table for each individual device below above chart - table: individual instances
    Instance | Date | Time | Duration (seconds) | Version | Auth type (online / offline) | Auth_sub_type | Outcome (success / failure) | IP | Network type | Error (if applicable) 
    01 | 2022-12-22 | 9:30am | 8.2 | Online | SMS | Success | 172.x.x.x | VPN | NA

A table summarising both online & offline info below above table - table: summaries
    prompt type | Success % | Success Count | Failure Count
    online | 90% | 90 | 10 
    offline | 90% | 90 | 10 

A line graph of all devices - average end to end for online and offline (calculation of ENTIRE LOG file): graph: cumulative

Total hostlist.txt report: 
    * online average
    * offline average

# TODO: add exception handling for scenario when there is no offline logins to average as it might bomb out @ point "p:"

Version 2.4:
* Add component / variable that captures duration of Okta auth times i.e. Verifies Okta times for each try: 
"2022-12-07 16:37:36.7484|Info|Initializing Okta Authentication."
* Removes any MFA instance that takes longer than 5 minutes (300 secs) - this provides better graphs. 
* Modify existing individual reports (tables) to include Okta auth times (including averages)
* Add new violin plot which graphs averages of entire log files for each host i.e. the last data point in 
the averaged report previously produced by version 2.3

Version 2.7 - 2023-07-04
Summary: 
Okta start ("Initializing Okta Authentication.") 
Okta end ("In ProcessAuthnResponse Status: SUCCESS") OR ("In ProcessAuthnResponse Status: MFA_REQUIRED")

Changes:
Remove adhoc directory creation, usage and functionality (no longer a requirement) - DONE
Add feature to check for existence of folders, if not then create - DONE
* In ProcessAuthnResponse Status: MFA_REQUIRED
* Factor type: push
* Factor type: sms
* In ProcessAuthnResponse Status: SUCCESS

Logic: 
Note that when calculating percentage for how many MFA challenge occurs (push, sms, offline) ensure to add each 
of its counts to the entire instance count before dividing the count by the sums.
"""
from datetime import datetime as dt
from datetime import time as t
import glob
import os
import time
import shutil
import pythonping
import plotly.graph_objects as go
import plotly.subplots as sp

# globals
processed = False # process only once a day?
hostlist = r".\hostlist.txt"
temporary_dir = r".\temp"
report_output = r".\report"
summarised_output = r".\output"
average_output_end_to_end = r".\average_output_end_to_end"
average_output_okta_to_end = r".\average_output_okta_to_end"
average_report = r".\average_report"
start_time = [23, 30]
end_time = [23, 59]

def obtain_raw_log_file_n_path(path):
    """check if new txt file has been copied for processing. Also grab timestamp file in directory.
    """
    file = max(glob.glob(os.path.join("{}".format(path), "*")), key=os.path.getmtime)
    timestamp = os.path.getmtime(file)
    return (file, timestamp)

def file_updated_previous_day(folder, file):
    try: 
        path = folder + file
        if os.path.exists(path):  
            creation_time = os.path.getmtime(path)
            diff = time.time() - creation_time 
        else: 
            return True # so as to initiate creation of file.
    except Exception as e: 
        print("s:", e)

    if diff >= 86400: # over 24 hours since last processed. 
        return True 
    else: 
        return False

def determine_network_type(ip): # based on IP address
    """
    10.x.x.x == SIM # change as required to indicate WWAN connection
    172.x.x.x == VPN # change as required to indicate company VPN
    # get IP range for all the different lans on the network? or all else being LAN or office wifi? 
    Return type of network
    """
    try: 
        if ip[:6] == "10.1.": # change as required to indicate WWAN IP
            return "4G"
        elif ip[:6] == "172.1" or ip[:6] == "172.2": # change as required to indicate company VPN IP address ranges
            return "VPN"
        else: # everything else i.e. lan office. 
            return "LAN"
    except Exception as e: 
        print("r1:", e) 

def create_nonexistent_directories(): 
    """
    Check for existence of output folders, if not create.
    """
    try: 
        if not os.path.exists(temporary_dir): 
            os.makedirs(temporary_dir)
        
        if not os.path.exists(report_output): 
            os.makedirs(report_output)
        
        if not os.path.exists(summarised_output): 
            os.makedirs(summarised_output)

        if not os.path.exists(average_output_end_to_end): 
            os.makedirs(average_output_end_to_end)

        if not os.path.exists(average_output_okta_to_end): 
            os.makedirs(average_output_okta_to_end)

        if not os.path.exists(average_report): 
            os.makedirs(average_report)

        if not os.path.exists(hostlist): 
            with open(hostlist, "w") as f: 
                pass
    except Exception as e: 
        print("create_nonexistent_directories:", e) 

def extract_hostname_from_path(path):
    hostname_line = ""
    with open(path, "r") as log:
        for line in log:
            if "machineName" in line:
                hostname_line = line
                break
    hostname_line = hostname_line.split(" ")
    for line in hostname_line:
        if "machineName" in line:
            return line[12:]
                
    return path[path.rfind("\\")+1:-3]

def extract_averages_from_file(mode, directory):
    """
    To be used with files in average_output_end_to_end directory & average_output_okta_to_end.
    returns temp{"hostname": [1.1, 2.2, 3.3, n], "hostname2": [5.5, n]} 
    """
    temp = dict()
    for host in os.listdir(directory):
        try:
            with open(os.path.join(directory, host), "r") as f:
                temp[host[:-4]] = []
                for line in f:
                    if mode == "summary": # end to end
                        listified_line = line.strip().split(",")
                        online_e2e_avg, offline_e2e_avg = listified_line[0], listified_line[1]
                        daily_avg_for_host = [float(online_e2e_avg), float(offline_e2e_avg)]
                        temp[host[:-4]].append(daily_avg_for_host)
                    elif mode == "okta": # okta to end
                        temp[host[:-4]] = float(line.strip())
        except Exception as e:
            print("o:", e)
    return {"Data": temp}

def process_log(path):
    """
    Rules: 
    # "Current selected factor:" blank means 'remember 24 hours' likely set while on VPN or 10.55.x.x
    # "TecMFA UI Initiated" marks the start of the instance 
    # look for |Error| 
        # Add to dictionary under ["Error]
    # Look for either: "=====" (Auth failed and instance concluded) OR online_success OR offline_success
    # "ONLINE_AUTHN_SUCCESS: Authenticated with Okta successfully OR 
        "OFFLINE_TOTP_AUTHN_SUCCESS: Authenticated with Offline Hardware TOTP."
        # means success
    # check 

    Shape of block (list of dictionaries) - each MFA instance is a dictionary:
    [
        {
            Instance: <used to plot instances in sequence> , 
            Date: <log entry>, Time: <log entry>, Version: <log entry>, 
            Auth_type: <online / offline>, Auth_sub_type: <24_or_office, sms_okta, push_okta>,
            Outcome: <succeeded / failed / timeout | cancelled>, IP: "", Network_type: <4G, LAN, VPN>, Errors: <row of error after |Error|>,
            End_to_end: <time in seconds>,
            Okta_to_end: <time in seconds> # Okta (online) to end of MFA instance
        }
    ]

    Averaged data: 
    Using above block, 

    returns list of summarised dictionaries (blocks)
    """

    def calc_section_times(prev, now):
        try:
            if prev != "" and now != "": 
                prev = dt.strptime(prev, "%H:%M:%S.%f")
                now = dt.strptime(now, "%H:%M:%S.%f")
                delta = now - prev
                return round(delta.total_seconds(),2)
            else: 
                return 0
        except Exception as e:
            print("d:", e)
            return 0

    def initialise_or_reset_block(): # an instance of MFA inside log file specified by activity between ==== rows.
        return {
            "Instance": 0, "Date": "", "Time": "", "Version": "8.1", "Auth_type": "", 
            "Auth_sub_type": "", "Outcome": "", "IP": "", "Network_type": "", "Errors": "", 
            "End_to_end": "", "Okta_to_end": ""
            }

    # Anomalies
    # to be used if no auth success (online or offline) - time stamp to be used to specify time taken without success
    spec_offline_initiate = "OfflineTOTP authentication user control loaded" # anomaly #1
    # anomaly - no auth success (on or offline) and no spec_offline_initiate - outcome of: failure 
    spec_online_failure = "Okta non recoverable error message label: Authentication Failed" # anomaly #2
    # anomaly #3 - not registered for offline! 
    spec_not_registered_for_offline = "Your computer is offline. Please register with any offline factor"
    # anomaly #4 - No offline enrollments exists for user - not yet used
    # 
    # anomaly #5 - PASSWORD_CHANGED: 
    spec_pw_changed = "PASSWORD_CHANGED:"

    spec_ip_check_1 = "XForwadedIP is sent through the request"
    spec_ip_check_2 = "localIP" # note if offline, no IP is specified

    # errors
    error_header = "|Error|"
    known_exceptions = [ # occurences of error code are followed by the worded errors in list, just for reference.
        "Your passCode doesn't match our records. Please try again.", # Error : Code - E0000068
        "Authentication Failed", # Error : Code - E0000004
        "An SMS message was recently sent. Please wait 30 seconds before trying again.", # Error : Code - E0000109
        "Your token doesn't match our records. Please try again." # Error : Code - E0000068 
        ]

    # constants i.e. doesn't change for the entire log
    entire_log = [] # holds dictionaries as specified in the block (initialise_or_reset_block) - later to be processed for averaging
    hostname = extract_hostname_from_path(path)
    username = "-" # identified once per entire log not inside block

    error_count = 0
    instance_count = 0

    # initialised to 0 so not to get reference before creation exception
    d_start = ""
    t_start = ""
    d_end = ""
    t_end = ""
    d_contingency_end = ""
    t_contingency_end = ""
    okta_start_date = "" # stub
    okta_start_time = ""
    okta_end_date = "" # stub
    okta_end_time = ""

    flag_mfa = False
    flag_local_user = False # used to exclude from collection & analysis - 2.6.6

    block = initialise_or_reset_block()

    with open(path, "r") as log:
        next(log) # skip the first line which is always =====
        
        n_minus_1 = "" 
        n_minus_2 = "" # typically "====="
        n_minus_3 = "" # typically last known entry for TecMFA instance
        
        for line in log:
            try:
                # Keep last 2 lines in memory
                n_minus_3 = n_minus_2 # n-3
                n_minus_2 = n_minus_1 # n-2
                n_minus_1 = line # current or n-1

                if "TecMFA UI Initiated" in line: # start of a new instance of authentication
                    if "=====" in n_minus_2: # Means block is finished: 
                        d_end, t_end = extract_date_time(n_minus_3)
                        elapsed_time = calc_section_times(prev=t_start, now=t_end)
                        if elapsed_time <= 0 or elapsed_time > 300: # extreme outliers / anomalies remove from report
                            pass
                        else: 
                            block["End_to_end"] = elapsed_time
                            # Check if empty, then fail otherwise succeed
                            if block["Outcome"] == "": 
                                block["Outcome"] = "Failed / Cancelled"

                            # Check if online (has IP)
                            if block["IP"] != "" and block["Auth_type"] != "Offline": 
                                block["Auth_type"] = "Online" 
                                okta_elapsed_time = calc_section_times(prev=okta_start_time, now=okta_end_time)
                                if okta_elapsed_time == 0: # failed to auth i.e. didn't get an okta time due to ERROR
                                    okta_elapsed_time = calc_section_times(prev=okta_start_time, now=t_end)
                                    block["Auth_sub_type"] = "24hr | Office" # Anomaly for blank output in report - comment out line to observe in report.
                                block["Okta_to_end"] = okta_elapsed_time
                            else: 
                                block["Auth_type"] = "Offline"

                            # Check if local user
                            if flag_local_user == False: 
                                instance_count += 1
                                block["Instance"] = instance_count
                                entire_log.append(block) # *********** ADD
                            else: 
                                flag_local_user = False

                        # Reset timers
                        okta_start_time = ""
                        okta_end_time = ""
                        t_start = ""
                        t_end = ""

                        flag_mfa = False
                        block = initialise_or_reset_block() # Reset
                    if "Version : v8.2" in line: # extract version
                        block["Version"] = "8.2"
                    d_start, t_start = extract_date_time(line)
                    block["Date"] = d_start 
                    block["Time"] = t_start[:-5]
                    # t_contingency_end = "" # reset contingency for each block! 
                elif "SAM value" in line: # username
                    username = extract_username(extract_log_entry(line)).strip()
                elif spec_ip_check_1 in line: # extract IP from localIP line
                    block["IP"] = extract_ip_1(extract_log_entry(line)).strip()
                    block["Network_type"] = determine_network_type(block["IP"]) # SIM, VPN or LAN
                elif spec_ip_check_2 in line: # extract IP from XForwardedIP line
                    block["IP"] = extract_ip_2(extract_log_entry(line)).strip()
                    block["Network_type"] = determine_network_type(block["IP"]) # SIM, VPN or LAN
                elif error_header in line: # look for and process |Error|
                    error_count += 1 
                    block["Errors"] += extract_log_entry(line)[1:] + "<br>" # add error to Error list of block 
                elif "ONLINE_AUTHN_SUCCESS: Authenticated with Okta successfully." in line: # SUCCESS - online
                    block["Auth_type"] = "Online"
                    d_end, t_end = extract_date_time(line) # calculate end time for instance
                    if flag_mfa == False:
                        okta_end_time = t_end
                    block["End_to_end"] = calc_section_times(prev=t_start, now=t_end)
                    block["Outcome"] = "Success"
                elif "OFFLINE_TOTP_AUTHN_SUCCESS: Authenticated with Offline Hardware TOTP." in line: # SUCCESS - offline
                    block["Auth_type"] = "Offline"
                    d_end, t_end = extract_date_time(line) # calculate end time for instance
                    block["End_to_end"] = calc_section_times(prev=t_start, now=t_end)
                    block["Outcome"] = "Success"
                elif "Current selected factor:" in line: # check auth sub type - only occurs after online_success
                    block["Auth_sub_type"] = extract_current_selected_factor(extract_log_entry(line))
                elif spec_offline_initiate in line: # used as contingency to missing on/off successful auth
                    d_contingency_end, t_contingency_end = extract_date_time(line)
                elif spec_online_failure in line: # online failure
                    d_end, t_end = extract_date_time(line)
                elif spec_not_registered_for_offline in line: # failure - no offline mechanism registered! 
                    d_end, t_end = extract_date_time(line)
                elif spec_pw_changed in line: # failure - anomaly #4
                    d_end, t_end = extract_date_time(line)
                elif "Initializing Okta Authentication" in line: # Okta start - mark start of OKTA process - 2.6.6
                    okta_start_date, okta_start_time = extract_date_time(line)
                elif "In ProcessAuthnResponse Status: MFA_REQUIRED" in line: # mark start of MFA required OKTA response - i.e. otherwise would be end of non-MFA OKTA process 2.6.6
                    okta_end_date, okta_end_time = extract_date_time(line)
                    flag_mfa = True
                elif "Bypassing TecMFA for local users." in line: 
                    flag_local_user = True
            except Exception as e:
                print("err", e)
    return {"Data": entire_log, "Username": username, "Hostname": hostname} # for averaging with another function

def calculate_summary_table_data(block): 
    """
    Takes calculated block and returns data for creating table (2nd table)
    """
    summary = {
        "Block_instance_total": len(block["Data"]), 
        "Online": {
            "Count": 0, "Online_%": 0, "Success_%": 0, "Success_count": 0
            }, # "Online_%" calculated by dividing ["Online"]["Count"] divided by ["Block_instance_total"]
        "Offline": {
            "Count": 0, "Offline_%": 0, "Success_%": 0, "Success_count": 0
            }, # "Offline_%" calculated by dividing ["Offline"]["Count"] divided by ["Block_instance_total"]
        "Auth_sub_type": {
            "24hr_or_office_count": 0, "SMS:OKTA_count": 0, "PUSH:OKTA_count": 0
        },
        "Errors": {
            "Count": 0
        }, 
        "Network_type": {
            "4G_count": 0, "VPN_count": 0, "LAN_count": 0, 
            "4G_%": 0, "VPN_%": 0, "LAN_%": 0 # _% calculated by _count divided by ["Block_instance_total"]
        },
        "End_to_end_sums": {
            "Online": 0, "Offline": 0, 
        }, 
        "End_to_end_averages": { 
            "Online": 0, # ["End_to_end_sums"]["Online"] divided by ["Online"]["Count"]
            "Offline": 0 # ["End_to_end_sums"]["Offline"] divided by ["Offline"]["Count"]
        }, 
        "Okta_to_end_sums": 0, 
        "Okta_to_end_averages": 0 # ["Okta_to_end_sums"] divided by ["Online"]["Count"]
    }

    try: 
        for instance in block["Data"]:
            if instance["Auth_type"] == "Online": # Auth, outcomes & end_to_end sum
                summary["Online"]["Count"] += 1
                if instance["Outcome"] == "Success":
                    summary["Online"]["Success_count"] += 1
                    # TODO: check whether all online is equivalent to usage of Okta 
                try: 
                    summary["Okta_to_end_sums"] += float(instance["Okta_to_end"])
                except Exception as e:
                    print("x:", e)
                try: 
                    summary["End_to_end_sums"]["Online"] += float(instance["End_to_end"])
                except Exception as e: 
                    print("xx:", e)
            elif instance["Auth_type"] == "Offline": 
                summary["Offline"]["Count"] += 1 
                if instance["Outcome"] == "Success":
                    summary["Offline"]["Success_count"] += 1
                try: 
                    summary["End_to_end_sums"]["Offline"] += float(instance["End_to_end"])
                except Exception as e: 
                    print("y:", e)

            if instance["Auth_sub_type"] == "SMS:OKTA": # Auth sub types
                summary["Auth_sub_type"]["SMS:OKTA_count"] += 1
            elif instance["Auth_sub_type"] == "PUSH:OKTA": 
                summary["Auth_sub_type"]["PUSH:OKTA_count"] += 1
            elif instance["Auth_sub_type"] == "24hr | Office": 
                summary["Auth_sub_type"]["24hr_or_office_count"] += 1
            
            if instance["Network_type"] == "4G": # Network types
                summary["Network_type"]["4G_count"] += 1
            elif instance["Network_type"] == "VPN": 
                summary["Network_type"]["VPN_count"] += 1
            elif instance["Network_type"] == "LAN": 
                summary["Network_type"]["LAN_count"] += 1

            if len(instance["Errors"]) != 0: # Errors
                summary["Errors"]["Count"] += len(instance["Errors"])
    except Exception as e: 
        print("w:", e) 

    try: # Calculate end_to_end time averages 
        # 0 count check
        if summary["Online"]["Count"] != 0:
            summary["End_to_end_averages"]["Online"] = round(summary["End_to_end_sums"]["Online"] / summary["Online"]["Count"], 2) # elapsed time
            summary["Online"]["Online_%"] = round(summary["Online"]["Count"] / summary["Block_instance_total"] * 100, 1)
            summary["Online"]["Success_%"] = round(summary["Online"]["Success_count"] / summary["Online"]["Count"] * 100, 1)
            summary["Okta_to_end_averages"] = round(summary["Okta_to_end_sums"] / summary["Online"]["Count"], 2) # new! 

        # 0 count check
        if summary["Offline"]["Count"] != 0: 
            summary["End_to_end_averages"]["Offline"] = round(summary["End_to_end_sums"]["Offline"] / summary["Offline"]["Count"], 2) # elapsed time
            summary["Offline"]["Offline_%"] = round(summary["Offline"]["Count"] / summary["Block_instance_total"] * 100, 1)
            summary["Offline"]["Success_%"] = round(summary["Offline"]["Success_count"] / summary["Offline"]["Count"] * 100, 1)

        # 0 count check 
        if summary["Network_type"]["4G_%"] != 0: 
            summary["Network_type"]["4G_%"] = round(summary["Network_type"]["4G_count"] / summary["Block_instance_total"] * 100, 1)
        if summary["Network_type"]["VPN_%"] != 0: 
            summary["Network_type"]["VPN_%"] = round(summary["Network_type"]["VPN_count"] / summary["Block_instance_total"] * 100, 1)
        if summary["Network_type"]["LAN_%"] != 0: 
            summary["Network_type"]["LAN_%"] = round(summary["Network_type"]["LAN_count"] / summary["Block_instance_total"] * 100, 1)
    except Exception as e: 
        print("z:", e)

    """ Sample output of summary: - v2.6.6 - Auth_sub_type is applicable for only Okta types.
    {
        'Block_instance_total': 144, 
        'Online': {'Count': 118, 'Online_%': 0.8194444444444444, 'Success_%': 0.9491525423728814, 'Success_count': 112}, 
        'Offline': {'Count': 26, 'Offline_%': 0.18055555555555555, 'Success_%': 1.0, 'Success_count': 26}, 
        'Auth_sub_type': {'24hr_or_office_count': 81, 'SMS:OKTA_count': 31, 'PUSH:OKTA_count': 22}, 
        'Errors': {'Count': 56}, 
        'Network_type': {'4G_count': 4, 'VPN_count': 84, 'LAN_count': 31, '4G_%': 0.027777777777777776, 'VPN_%': 0.5833333333333334, 'LAN_%': 0.2152777777777778}, 
        'End_to_end_sums': {'Online': 1820.3257000000006, 'Offline': 684.8079999999999}, 
        'End_to_end_averages': {'Online': 15.426488983050852, 'Offline': 26.338769230769227}},
        'Okta_to_end_sums': 450.55, 
        'Okta_to_end_averages': 3.128819444444444

    """
    return summary

def generate_hostlist(hostlist):
    """
    Modify .\hostlist.txt - will check if file has changed, if it has will process
    each and host listed on each like of the file. 
    """
    try:
        hosts = dict()
        with open(hostlist, "r") as f:
            for host in f:
                hosts[host.strip()] = False
        return hosts
    except Exception as e:
        print("i:", e)

def all_hosts_processed(hostlist):
    """
    Return True if all hosts in hostlist_status are True.
    Works in conjunction with generate_hostlist function.
    """
    try:
        for host in hostlist:
            if hostlist[host] == False:
                return False
        return True # no hosts left to process
    except Exception as e:
        print("c:", e)

def commit_summarised_data_to_file(summary, latest_log):
    """
    Write to txt file output from process_log function.
    data: list of dictionaries.
    Shape of txt file, two only: ["End_to_end_averages"]["Online"], ["End_to_end_averages"]["Offline"]
    """
    hostname = extract_hostname_from_path(latest_log)

    try: 
        temp = ""
        if file_updated_previous_day(r"./average_output_end_to_end", hostname):
            with open(r".\average_output_end_to_end\{}.txt".format(hostname), "a+") as f:
                temp += str(summary["End_to_end_averages"]["Online"]) + "," + str(summary["End_to_end_averages"]["Offline"]) # version 2.3
                f.write(temp + "\n")
    except Exception as e:
        print("Commit_summarised_data_to_file - summary:", e)
    try: 
        temp = ""
        if file_updated_previous_day(r"./average_output_okta_to_end", hostname):
            with open(r".\average_output_okta_to_end\{}.txt".format(hostname), "w") as f: # only one val required
                temp = str(summary["Okta_to_end_averages"]) # version 2.4
                f.write(temp + "\n")
    except Exception as e:
        print("Commit_summarised_data_to_file - Okta:", e)
            
def plot_graph(mode, block, summary=None):
    """
    Parameters: 
    Block: processed_device_block, device_summarised or cumulative_devices_summary - depending on type of output desired.
    Mode:
    "graph: individual host" - includes 2 tables in addition to line graph.
    "graph: cumulative" - reads txt files from average_output_end_to_end & okta_to_end directories to craft line graph
    """

    headerColor = "grey"
    rowEvenColor = "lightgrey"
    rowOddColor = "white"

    x_axis = []
    datapoint = 0 # x i.e. instances
    end_to_end = []
    okta_to_end = []
    
    if mode == "graph: individual host": # includes two other tables. 
        username = block["Username"]
        hostname = block["Hostname"]
    
        try: 
            for instance in block["Data"]:
                datapoint += 1
                x_axis.append(datapoint)
                end_to_end.append(instance["End_to_end"])
                okta_to_end.append(instance["Okta_to_end"])
        except Exception as e: 
            print("e3:", e)

        try: # table: individual instances or the device
            table_individual_instances = go.Table(
                header=dict(values=[
                    "#", "Date", "Time", "Duration (secs)", "Version", "Auth type", 
                    "Online auth", "Okta duration (secs)", "Outcome", "IP", "Network", "Errors"
                    ],
                    line_color="darkslategray", 
                    fill_color=headerColor,
                    align="center",
                    font=dict(color='white', size=15)
                ), 
                cells=dict(values=[
                    [val["Instance"] for val in block["Data"]], 
                    [val["Date"] for val in block["Data"]], 
                    [val["Time"] for val in block["Data"]], 
                    [val["End_to_end"] for val in block["Data"]], 
                    [val["Version"] for val in block["Data"]], 
                    [val["Auth_type"] for val in block["Data"]], 
                    [val["Auth_sub_type"] for val in block["Data"]], 
                    [val["Okta_to_end"] for val in block["Data"]],
                    [val["Outcome"] for val in block["Data"]], 
                    [val["IP"] for val in block["Data"]], 
                    [val["Network_type"] for val in block["Data"]], 
                    [val["Errors"] for val in block["Data"]]
                    ],
                    line_color="darkslategray", 
                    fill_color = [[rowOddColor,rowEvenColor,rowOddColor, rowEvenColor,rowOddColor]*5],
                    align=["center","center","center","center","center","center","center","center","center","center","center","left"],
                    font = dict(color = 'darkslategray', size = 13)
                ), 
                columnwidth=[1,2,2,2,2,2,2,2,2,2,2,10]
            )
        except Exception as e: 
            print("t:", e)

        try: # table: summarised for entire device log 
            table_summary_auth = go.Table(
                header=dict(values=[
                    "Auth count", "Online %", "Offline %", "Online success %", "Offline success %", "Avg Online duration (sec)", 
                    "Avg Offline duration (sec)", "Avg Okta duration (sec)", "4G %", "VPN %", "LAN %"
                    ],
                    line_color='darkslategray',
                    fill_color='lightskyblue',
                    align="center", 
                    font=dict(color='darkslategray', size=15)
                ), 
                cells=dict(values=[
                    [summary["Block_instance_total"]],
                    [summary["Online"]["Online_%"]], 
                    [summary["Offline"]["Offline_%"]],
                    [summary["Online"]["Success_%"]],
                    [summary["Offline"]["Success_%"]],
                    [summary["End_to_end_averages"]["Online"]],
                    [summary["End_to_end_averages"]["Offline"]],
                    [summary["Okta_to_end_averages"]],
                    [summary["Network_type"]["4G_%"]],
                    [summary["Network_type"]["VPN_%"]], 
                    [summary["Network_type"]["LAN_%"]]
                ],
                    line_color='darkslategray',
                    fill_color='lightcyan',
                    align="center", 
                    font=dict(color='darkslategray', size=13)
                ), 
                columnwidth=[1,2,2,2,2,2,2,2,2,2,2,2,2,2,2]
            )
        except Exception as e: 
            print("t2:", e)

        try: # build and export the report which includes the graph and 2x tables.
            fig = sp.make_subplots( # https://plotly.com/python/table-subplots/
                rows=9,
                cols=1, 
                specs=[
                    [{"type": "xy", "rowspan": 4}], 
                    [{"type": "xy"}], 
                    [{"type": "xy"}], 
                    [{"type": "xy"}], 
                    [{"type": "table", "rowspan": 3}],
                    [{"type": "table"}], 
                    [{"type": "table"}],
                    [{"type": "table", "rowspan": 2}],
                    [{"type": "table"}]
                ],
                vertical_spacing=0.06
            )
            # line graph
            fig.add_trace(go.Scatter(
                    x = x_axis,
                    y = end_to_end,
                    name="End to end duration (sec)",
                    marker=dict(size=3),
                    line=dict(width=1)
                    ), row=1, col=1, 
                )
            fig.add_trace(go.Scatter(
                    x = x_axis, 
                    y = okta_to_end, 
                    name="Okta response duration (sec)",
                    marker=dict(size=3),
                    line=dict(width=1)
                    ), row=1, col=1, 
                )
            fig.add_trace(table_individual_instances, row=5, col=1) # table 1
            fig.add_trace(table_summary_auth, row=8, col=1) # table 2
            
            fig.update_layout(
                title = hostname + "//" + username,
                xaxis_title = "End to end times for TechMFA instances",
                yaxis_title = "Time (sec)",
                legend_title = "Legend",
                font=dict(
                    family = "Courier New, monospace",
                    size = 18,
                    color = "RebeccaPurple"
                    ), 
                height=2500
                )
            fig.write_html(r".\report\{}.html".format(hostname)) # write report to directory
        except Exception as e: 
            print("plot err:", e)
        
    elif mode == "graph: cumulative": # cumulative_devices_summary
        try:
            fig = go.Figure()
            for host in block["Data"]: # device_summarised
                datapoint = 0 
                x_axis = [] 
                averages_online = [] 
                averages_offline = [] 

                for list_of_two_averages in block["Data"][host]:
                    datapoint += 1
                    x_axis.append(datapoint)
                    averages_online.append(list_of_two_averages[0])
                    averages_offline.append(list_of_two_averages[1])
                
                fig.add_trace(
                    go.Scatter(
                        x = x_axis[:],
                        y = averages_online[:],
                        name = host + ": " + "Online avg", # mojo
                        marker=dict(size=3),
                        line=dict(width=1)
                        )
                    )
                
                fig.add_trace(
                    go.Scatter(
                        x = x_axis[:], 
                        y = averages_offline[:],
                        name = host + ": " + "Offline avg",
                        marker=dict(size=3),
                        line=dict(width=1)
                    )
                )

            fig.update_layout(
                title = "Daily snapshot of end-to-end average (online & offline) based on entire log (per host)",
                xaxis_title = "Snapshot (daily)",
                yaxis_title = "Time (sec)",
                legend_title = "Legend",
                font=dict(
                    family = "Courier New, monospace",
                    size=18,
                    color = "RebeccaPurple"
                    )
                )
            fig.write_html(r".\average_report\total_averages.html")
        except Exception as e:
            print("p:", e)

    elif mode == "graph: violin": 
        try: 
            list_of_log_avgs = [] # contains average okta times as calculated for each host/log.
                        
            for host in block["Data"]: # device_summarised
                list_of_log_avgs.append(block["Data"][host])

            fig = go.Figure(
                data=go.Violin(
                    x=list_of_log_avgs, 
                    box_visible=True,
                    meanline_visible=True,
                    points="all",
                    orientation="h",
                    jitter=0.05,
                    pointpos=0,
                    marker=dict(size=3),
                    line_color="black",
                    fillcolor="#636EFA",
                    opacity=0.6,
                    name="",
                    )
                )

            fig.update_layout(
                title = "Okta authentication duration averages based on entire log (per host)",
                yaxis_title = "Tenancy",
                xaxis_title = "Time (sec)",
                font=dict(
                    family = "Courier New, monospace",
                    size=18,
                    color = "RebeccaPurple"
                    )
                )
            fig.write_html(r".\average_report\okta_averages_violin.html")
        except Exception as e: 
            print("p2:", e)

def active_time_range(start, end): # time range during which hostlist.txt is processed
    now = dt.now().time()
    if now > t(start[0], start[1]) and now < t(end[0], end[1]): # now > 11:30AM AND < 2:00PM
        return True
    else:
        return False

def map_source_location(source):
    try:
        os.system(r"NET USE Z: /DELETE /yes")
    except Exception as e:
        print("failed to remove mapped drive Z:")
    try:
        x = os.system(r"NET USE Z: {source} /persistent:No".format(source=source))
        return True
    except Exception as e:
        print("a:", e)
        return False

def ping_host(d):
    try:
        result = pythonping.ping(d.strip(), timeout=2, count=2)
        if result.success():
            return True
    except Exception as e:
        # print("b:", e)
        return False

def extract_current_selected_factor(line): 
    """
    Only occurs after Online authentication. 
    Entry beyond |Info|
    can be three outcomes: 
        Current selected factor: sms:OKTA
        Current selected factor: push:OKTA
        Current selected factor: # blank i.e. remember for 24 hours OR logging in from office
    Returns value depending on log entry.
    """
    temp = line[24:]
    if "sms:OKTA" in temp: 
        return "SMS:OKTA"
    elif "push:OKTA" in temp: 
        return "PUSH:OKTA"
    else: # blank
        return "24hr | Office"

def extract_date_time(line):
    try: 
        index = line.find("|Info|")
        if index == -1:
            index = line.find("|Error|")
        return line[:index].split(" ")
    except Exception as e:
        print("v:", e)
    
def extract_log_entry(line):
    return line[30:]

def extract_ip_1(line): 
    return line[42:]

def extract_ip_2(line):
    return line[10:]

def extract_username(line):
    return line[12:]

def previous_reset_time(prev, now):
    if last_run == None: # first run
        return True 
    else: 
        difference = dt.now() - prev
        if difference.total_seconds() >= 86400: # 24 hours
            return True
        else:
            return False

if __name__ == "__main__": 
    last_run = None
    while True:
        try:
            time.sleep(10)
            print("Snoozing...")
            if active_time_range(start=start_time, end=end_time):
                create_nonexistent_directories() 
                if previous_reset_time(last_run, dt.now()): # 24 hours elapsed
                    last_run = dt.now()
                    hostlist_status = generate_hostlist(hostlist) # all initialised as false
                    while not all_hosts_processed(hostlist_status):
                        time.sleep(5)
                        try: 
                            if not active_time_range(start=start_time, end=end_time): 
                                break # ensure schedule runs in window only
                            else: # greenlight
                                for device in hostlist_status:
                                    if hostlist_status[device] == False: # not yet processed
                                        if ping_host(device): # pingable
                                            if map_source_location(r"\\{}\c$".format(device)): # map to location # copy
                                                try: 
                                                    shutil.copyfile(
                                                        r"Z:\Program Files\TecMFA\Logs\TecMFALogs.txt", r"{}\TecMFALogs.txt".format(temporary_dir)
                                                        )
                                                    print("{}, log file copied to temporary location for processing".format(device))
                                                except Exception as e:
                                                    # print("Unable to copy log file:{}".format(device), e) # debug
                                                    continue
                                                device_log = obtain_raw_log_file_n_path(temporary_dir)[0]
                                                
                                                processed_device_block = process_log(device_log) # main processing, returns block

                                                device_summarised = calculate_summary_table_data(processed_device_block)

                                                commit_summarised_data_to_file(
                                                    summary=device_summarised, latest_log=device_log
                                                    ) # used for cummulative chart - (online end to end avg, offline end to end avg)
                                                
                                                plot_graph(mode="graph: individual host", block=processed_device_block, summary=device_summarised)

                                                hostlist_status[device] = True # mark as done
                                            else:
                                                continue
                        except Exception as e:
                            print("q:", e)
                        remaining_hosts = [h for h in hostlist_status if h == False]
                        print("Number of remaining hosts in hostlist that weren't processed:", len(remaining_hosts))
                        print("Remaining hosts that cannot be processed:", remaining_hosts)
                    print("Either all hosts processed or have exceeded active time window")
                    print("Hostlist status as follows: {}".format(hostlist_status))
                else:
                    time.sleep(5)
                    continue

                try:
                    print("Outside of active time range: {} to {}".format(start_time, end_time))
                    cumulative_devices_summary = extract_averages_from_file("summary", average_output_end_to_end) # == {hostname: [[1,2],[2,3], n], hostname2: [[1,2],[2,3], n]}
                    cumulative_okta_end_to_end_summary = extract_averages_from_file("okta", average_output_okta_to_end)
                    print("Processing average report.")
                    plot_graph(mode="graph: cumulative", block=cumulative_devices_summary)
                    plot_graph(mode="graph: violin", block=cumulative_okta_end_to_end_summary)
                except Exception as e:
                    print("r:", e)

                time.sleep(5)
        except Exception as e:
            print("m:", e)
            time.sleep(3)
