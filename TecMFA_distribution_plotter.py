# HZH
# Version: 0.1
# Date: 2023-05-03

from datetime import datetime as dt
from datetime import time as t
import os
import plotly.graph_objects as go
import plotly.subplots as sp
import numpy as np

tenancy_a_dir = r".\xxx" # change xxx to appropriate tenancy directory name
tenancy_b_dir = r".\yyy" # change yyy to appropriate tenancy directory name

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

def plot_graph(mode, tenancy_a, tenancy_b):
    """
    Parameters: 
    tenancy_a: processed_device_block, device_summarised or cumulative_devices_summary - depending on type of output desired.
    tenancy_b: same as tenancy_a but for tenancy_b
    Mode:
    "graph: individual host" - includes 2 tables in addition to line graph.
    "graph: cumulative" - reads txt files from average_output_end_to_end & okta_to_end directories to craft line graph
    """
    
    if mode == "graph: violin": 
        try: 
            tenancy_a_list_of_logs = [] # contains average okta times as calculated for each host/log.
            tenancy_b_list_of_logs = [] # contains average okta times as calculated for each host/log.

            for host in tenancy_a["Data"]: # device_summarised
                tenancy_a_list_of_logs.append(tenancy_a["Data"][host])

            for host in tenancy_b["Data"]: 
                tenancy_b_list_of_logs.append(tenancy_b["Data"][host])

            trace1 = go.Violin(
                    x=tenancy_a_list_of_logs, 
                    y=np.repeat("tenancy_a", len(tenancy_a_list_of_logs)),
                    box_visible=True,
                    meanline_visible=True,
                    points="all",
                    orientation="h",
                    jitter=0.1,
                    pointpos=0,
                    marker=dict(size=1),
                    line_color="black",
                    fillcolor="#50D1E5",
                    opacity=0.6,
                    )
            
            trace2 =go.Violin(
                    x=tenancy_b_list_of_logs, 
                    y=np.repeat("tenancy_b", len(tenancy_b_list_of_logs)),
                    box_visible=True,
                    meanline_visible=True,
                    points="all",
                    orientation="h",
                    jitter=0.1,
                    pointpos=0,
                    marker=dict(size=1),
                    line_color="black",
                    fillcolor="#50D1E5",
                    opacity=0.6,
                    )
                
            fig = go.Figure(
                data=[trace2, trace1]
                )
            
            fig.update_layout(
                title = "Okta authentication duration averages based on entire log (per host)",
                yaxis_title = "",
                xaxis_title = "Time (sec)",
                showlegend=False,
                font=dict(
                    family = "Courier New, monospace",
                    size=18,
                    color = "RebeccaPurple"
                ),
                xaxis=dict(
                    tickmode="linear", 
                    dtick=5,
                    gridcolor="lightgray",
                    gridwidth=1,
                )
            )
            fig.write_html(r".\average_report\okta_averages_violin.html")
        except Exception as e: 
            print("p2:", e)

tenancy_a_okta_data = extract_averages_from_file("okta", tenancy_a_dir)
tenancy_b_okta_data = extract_averages_from_file("okta", tenancy_b_dir)

plot_graph(mode="graph: violin", tenancy_a=tenancy_a_okta_data, tenancy_b=tenancy_b_okta_data)
