AT_COMMANDS = {
    "init_gprs": [
        'AT+SAPBR=3,1,"CONTYPE","GPRS"',
        'AT+SAPBR=3,1,"APN","internet"',
        'AT+SAPBR=1,1',
        'AT+SAPBR=2,1'
    ],
    "get_operator": 'AT+COPS?',
    "get_phone": 'AT+CNUM',
    "get_balance": 'AT+CUSD=1,"*100#",15',
}
