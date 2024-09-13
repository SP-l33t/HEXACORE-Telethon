import re


def get_sec_ch_ua(user_agent):
    pattern = r'(Chrome|Chromium)\/(\d+)\.(\d+)\.(\d+)\.(\d+)'

    match = re.search(pattern, user_agent)

    if match:
        browser = match.group(1)
        version = match.group(2)

        if browser == 'Chrome':
            sec_ch_ua = f'"Chromium";v="{version}", "Not;A=Brand";v="24", "Google Chrome";v="{version}"'
        else:
            sec_ch_ua = f'"Chromium";v="{version}", "Not;A=Brand";v="24"'

        return {'Sec-Ch-Ua': sec_ch_ua}
    else:
        return {}


headers = {
    'Accept': '*/*',
    'Accept-Language': 'ru-RU,ru;q=0.9',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://ago-wallet.hexacore.io',
    'Referer': 'https://ago-wallet.hexacore.io/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'Sec-Ch-Ua-Mobile': '?1',
    'Sec-Ch-Ua-Platform': '"Android"',
}
