health_response = '''[
    {
        "Checks": [
            {
                "CheckID": "service:instrument_driver_RS10ENGC-XX00X-00-SPKIRA001",
                "Name": "Service 'instrument_driver' check",
                "Node": "uft21",
                "Notes": "",
                "Output": "",
                "ServiceID": "instrument_driver_RS10ENGC-XX00X-00-SPKIRA001",
                "ServiceName": "instrument_driver",
                "Status": "passing"
            },
            {
                "CheckID": "serfHealth",
                "Name": "Serf Health Status",
                "Node": "uft21",
                "Notes": "",
                "Output": "Agent alive and reachable",
                "ServiceID": "",
                "ServiceName": "",
                "Status": "passing"
            }
        ],
        "Node": {
            "Address": "128.6.240.39",
            "Node": "uft21"
        },
        "Service": {
            "Address": "",
            "ID": "instrument_driver_RS10ENGC-XX00X-00-SPKIRA001",
            "Port": 42558,
            "Service": "instrument_driver",
            "Tags": [
                "RS10ENGC-XX00X-00-SPKIRA001"
            ]
        }
    },
    {
        "Checks": [
            {
                "CheckID": "service:instrument_driver_RS10ENGC-XX00X-00-TMPSFA001",
                "Name": "Service 'instrument_driver' check",
                "Node": "uft21",
                "Notes": "",
                "Output": "",
                "ServiceID": "instrument_driver_RS10ENGC-XX00X-00-TMPSFA001",
                "ServiceName": "instrument_driver",
                "Status": "passing"
            },
            {
                "CheckID": "serfHealth",
                "Name": "Serf Health Status",
                "Node": "uft21",
                "Notes": "",
                "Output": "Agent alive and reachable",
                "ServiceID": "",
                "ServiceName": "",
                "Status": "passing"
            }
        ],
        "Node": {
            "Address": "128.6.240.39",
            "Node": "uft21"
        },
        "Service": {
            "Address": "",
            "ID": "instrument_driver_RS10ENGC-XX00X-00-TMPSFA001",
            "Port": 41799,
            "Service": "instrument_driver",
            "Tags": [
                "RS10ENGC-XX00X-00-TMPSFA001"
            ]
        }
    }
]'''

port_agent_response = '''[
    {
        "Checks": [
            {
                "CheckID": "service:port-agent-RS10ENGC-XX00X-00-BOTPTA001",
                "Name": "Service 'port-agent' check",
                "Node": "uft21",
                "Notes": "",
                "Output": "",
                "ServiceID": "port-agent-RS10ENGC-XX00X-00-BOTPTA001",
                "ServiceName": "port-agent",
                "Status": "passing"
            },
            {
                "CheckID": "serfHealth",
                "Name": "Serf Health Status",
                "Node": "uft21",
                "Notes": "",
                "Output": "Agent alive and reachable",
                "ServiceID": "",
                "ServiceName": "",
                "Status": "passing"
            }
        ],
        "Node": {
            "Address": "128.6.240.39",
            "Node": "uft21"
        },
        "Service": {
            "Address": "",
            "ID": "port-agent-RS10ENGC-XX00X-00-BOTPTA001",
            "Port": 41347,
            "Service": "port-agent",
            "Tags": [
                "RS10ENGC-XX00X-00-BOTPTA001"
            ]
        }
    }
]'''
