import aiohttp
import asyncio
import json
import re
from urllib.parse import unquote, parse_qs
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from random import uniform, randint
from time import time

from bot.utils.universal_telegram_client import UniversalTelegramClient

from .headers import *
from bot.config import settings
from bot.utils import logger, log_error, config_utils, CONFIG_PATH, first_run
from bot.exceptions import InvalidSession

HEXA_DOMAIN = "https://ago-api.hexacore.io"


class Tapper:
    def __init__(self, tg_client: UniversalTelegramClient):
        self.tg_client = tg_client
        self.session_name = tg_client.session_name

        session_config = config_utils.get_session_config(self.session_name, CONFIG_PATH)

        if not all(key in session_config for key in ('api', 'user_agent')):
            logger.critical(self.log_message('CHECK accounts_config.json as it might be corrupted'))
            exit(-1)

        self.headers = headers
        user_agent = session_config.get('user_agent')
        self.headers['user-agent'] = user_agent
        self.headers.update(**get_sec_ch_ua(user_agent))

        self.proxy = session_config.get('proxy')
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            self.tg_client.set_proxy(proxy)

        self.user_data = None
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.time_end = 0
        self.ref_id = None

        self._webview_data = None

    def log_message(self, message) -> str:
        return f"<ly>{self.session_name}</ly> | {message}"

    async def get_tg_web_data(self) -> str:
        webview_url = await self.tg_client.get_app_webview_url('HexacoinBot', "wallet", "525256526")

        tg_web_data = unquote(string=webview_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])
        user_data = json.loads(parse_qs(tg_web_data).get('user', [''])[0])
        query_params = parse_qs(tg_web_data)
        self.ref_id = query_params.get('start_param', [''])[0]

        self.user_id = user_data.get('id')
        self.first_name = user_data.get('first_name')
        self.last_name = user_data.get('last_name')
        self.username = user_data.get('username')

        self.fullname = f'{self.first_name} {self.last_name}'.strip()

        return tg_web_data

    async def auth(self, http_client: CloudflareScraper, init_data):
        try:
            json = {"data": init_data}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/app-auth', json=json)
            response.raise_for_status()
            response_json = await response.json()
            return response_json.get('token')
        except Exception as error:
            log_error(self.log_message(f"Error while auth {error}"))
            return

    async def register(self, http_client: CloudflareScraper, init_data):
        try:
            auth_token = await self.auth(http_client=http_client, init_data=init_data)
            if not auth_token:
                raise ConnectionError('Failed to get auth token')
            http_client.headers['Authorization'] = auth_token

            if self.username != '':
                json = {
                    "user_id": int(self.user_id),  # Ensure user_id is a string
                    "fullname": f"{str(self.fullname)}",
                    "username": f"{str(self.username)}"
                }
                if self.ref_id:
                    json["referer_id"] = str(self.ref_id)
                response = await http_client.get(url=f'{HEXA_DOMAIN}/api/user-exists?country_code=null')
                res = await response.json()
                if res.get('exists') is True:
                    return True

                response = await http_client.post(url=f'{HEXA_DOMAIN}/api/create-user', json=json)

                if response.status == 409:
                    return 'registered'
                if response.status in (200, 201):
                    return True
                if response.status not in (200, 201, 409):
                    log_error(self.log_message(f"Something wrong with register! {response.status}."))
                    return False
            else:
                log_error(self.log_message(f"Error while register, please add username to telegram account"))
                return False
        except ConnectionError as error:
            raise error
        except Exception as error:
            log_error(self.log_message(f"Error while register {error}"))
            return False

    async def get_taps(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/available-taps')
            response_json = await response.json()
            taps = response_json.get('available_taps')
            boosters = response_json.get('available_boosters')
            return taps, boosters
        except Exception as error:
            log_error(self.log_message(f"Error while get taps {error}"))

    async def get_balance(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/balance/{self.user_id}')
            response_json = await response.json()
            return response_json
        except Exception as error:
            log_error(self.log_message(f"Error while get balance {error}"))

    async def do_taps(self, http_client: CloudflareScraper, taps):
        try:
            json = {"taps": taps}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/mining-complete', json=json)
            response_json = await response.json()

            if not response_json.get('success'):
                return False

            return True

        except Exception as error:
            log_error(self.log_message(f"Error while do taps {error}"))

    async def use_booster(self, http_client: CloudflareScraper):
        try:
            response = await http_client.post(f"{HEXA_DOMAIN}/api/activate-boosters")
            resp_json = await response.json()
            success = resp_json.get('success')
            return success
        except Exception as error:
            log_error(self.log_message(f"Error while trying to use buster - {error}"))

    async def get_missions(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/missions')
            response_json = await response.json()
            incomplete_mission_ids = [mission['id'] for mission in response_json if (not mission['isCompleted']
                                                                                     and mission['autocomplete'])]

            return incomplete_mission_ids
        except Exception as error:
            log_error(self.log_message(f"Error while get missions {error}"))
            return []

    async def do_mission(self, http_client: CloudflareScraper, id):
        try:
            json = {'missionId': id}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/mission-complete', json=json)
            response_json = await response.json()
            if not response_json.get('success'):
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while doing missions {error}"))

    async def get_level_info(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/level')
            response_json = await response.json()
            response.raise_for_status()
            lvl = response_json.get('lvl')
            upgrade_available = response_json.get('upgrade_available', None)
            upgrade_price = response_json.get('upgrade_price', None)
            new_lvl = response_json.get('next_lvl', None)
            return lvl, upgrade_available, upgrade_price, new_lvl
        except Exception as error:
            log_error(self.log_message(f"Error while get level {error}"))

    async def level_up(self, http_client: CloudflareScraper):
        try:
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/upgrade-level')
            response_json = await response.json()
            if not response_json.get('success'):
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while up lvl {error}"))

    async def play_game_1(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/in-game-reward-available/1/{self.user_id}')
            response_json = await response.json()
            if response_json.get('available'):
                json = {"game_id": 1, "user_id": self.user_id}
                response1 = await http_client.post(url=f'{HEXA_DOMAIN}/api/in-game-reward', json=json)
                if response1.status in (200, 201):
                    return True
            else:
                return False

        except Exception as error:
            log_error(self.log_message(f"Error while play game 1 {error}"))

    async def play_game_2(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/in-game-reward-available/2/{self.user_id}')
            response_json = await response.json()
            if response_json.get('available'):
                json = {"game_id": 2, "user_id": self.user_id}
                response1 = await http_client.post(url=f'{HEXA_DOMAIN}/api/in-game-reward', json=json)
                if response1.status in (200, 201):
                    return True
            else:
                return False

        except Exception as error:
            log_error(self.log_message(f"Error while play game 2 {error}"))

    async def play_game_3(self, http_client: CloudflareScraper):
        try:
            response = await http_client.post(url=f'https://ago-api.hexacore.io/api/games/3/sessions/start')
            response = await http_client.get(url=f'https://dirty-job-server.hexacore.io/game/start?'
                                                 f'playerId={self.user_id}')
            text = await response.text()
            response.raise_for_status()
            response_json = await response.json()

            level = response_json.get('playerState').get('currentGameLevel')

            games_count = len(response_json.get('gameConfig').get('gameLevels', {}))

            for i in range(level + 1, games_count):
                json = {"type": "EndGameLevelEvent", "playerId": str(self.user_id), "level": int(i), "boosted": False,
                        "transactionId": None}
                response1 = await http_client.post(url=f'https://dirty-job-server.hexacore.io/game/end-game-level',
                                                   json=json)

                if response1.status in (200, 201):
                    logger.info(self.log_message(f"Done {i} lvl in dirty job"))

                elif response1.status == 400:
                    logger.warning(self.log_message(f"Reached max games for today in dirty job"))
                    break

                await asyncio.sleep(uniform(2, 5))

            balance = response_json.get('playerState').get('inGameCurrencyCount')
            owned_items = response_json.get('playerState').get('hubItems')
            available_items = response_json.get('gameConfig').get('hubItems')

            logger.info(self.log_message(f"Trying to upgrade items in dirty job, wait a bit"))

            old_auth = http_client.headers['Authorization']

            if http_client.headers['Authorization']:
                del http_client.headers['Authorization']

            for item_name, item_info in available_items.items():
                if item_name not in owned_items:
                    upgrade_level_info = list(map(int, item_info['levels'].keys()))
                    level_str = str(upgrade_level_info[0])
                    price = item_info['levels'][level_str]['inGameCurrencyPrice']
                    ago = item_info['levels'][level_str]['agoReward']

                    if balance >= price:
                        purchase_data = {
                            "type": "UpgradeHubItemEvent",
                            "playerId": str(self.user_id),
                            "itemId": str(item_name),
                            "level": int(upgrade_level_info[0])
                        }
                        purchase_response = await http_client.post(
                            url='https://dirty-job-server.hexacore.io/game/upgrade-hub-item',
                            json=purchase_data)

                        if purchase_response.status in (200, 201):
                            logger.success(self.log_message(f"Purchased new item {item_name} for {price} currency "
                                                            f"in dirty job game, got {ago} AGO"))
                            balance -= price
                            owned_items[item_name] = {'level': upgrade_level_info[0]}
                        else:
                            logger.warning(self.log_message(
                                f"Failed to purchase new item {item_name}. Status code: {purchase_response.status}, "
                                f"text: {await purchase_response.text()}, headers - \n{http_client.headers}"))

                elif item_name in owned_items:
                    current_level = int(owned_items[item_name]['level'])
                    upgrade_level_info = list(map(int, item_info['levels'].keys()))

                    next_levels_to_upgrade = [level for level in upgrade_level_info if level > current_level]

                    if not next_levels_to_upgrade:
                        continue

                    for level in next_levels_to_upgrade:
                        level_str = str(level)
                        price = item_info['levels'][level_str]['inGameCurrencyPrice']
                        ago = item_info['levels'][level_str]['agoReward']

                        if balance >= price:
                            purchase_data = {
                                "type": "UpgradeHubItemEvent",
                                "playerId": str({self.user_id}),
                                "itemId": str({item_name}),
                                "level": int(level)
                            }
                            purchase_response = await http_client.post(
                                url='https://dirty-job-server.hexacore.io/game/upgrade-hub-item',
                                json=purchase_data)

                            if purchase_response.status in (200, 201):
                                logger.success(self.log_message(f"Purchased upgrade for {item_name} for {price} "
                                                                f"currency in dirty job game, got {ago} AGO"))
                                balance -= price
                                owned_items[item_name]['level'] = level
                            else:
                                logger.warning(self.log_message(
                                    f"Failed to purchase upgrade for {item_name}. Status code: "
                                    f"{purchase_response.status}"))

                await asyncio.sleep(uniform(0.5, 1))

            http_client.headers['Authorization'] = old_auth
        except Exception as error:
            log_error(self.log_message(f"Error while play game 3 {error}"))

    async def play_game_5(self, http_client: CloudflareScraper):
        try:
            response = await http_client.post(f"{HEXA_DOMAIN}/api/games/5/sessions/start")
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/in-game-reward-available/5/{self.user_id}')
            response_json = await response.json()
            if response_json.get('available'):
                json = {"game_id": 5, "user_id": self.user_id}
                response1 = await http_client.post(url=f'{HEXA_DOMAIN}/api/in-game-reward', json=json)
                if response1.status in (200, 201):
                    return True
            else:
                return False

        except Exception as error:
            log_error(self.log_message(f"Error while play game 5 {error}"))

    async def play_game_6(self, http_client: CloudflareScraper):
        try:
            old_auth = http_client.headers['Authorization']

            response = await http_client.post("https://ago-api.hexacore.io/api/games/6/sessions/start")

            http_client.headers['Authorization'] = str(self.user_id)

            response = await http_client.get(url=f'https://hurt-me-please-server.hexacore.io/game/start')
            response.raise_for_status()
            response_json = await response.json()

            current_level = response_json.get('playerState').get('currentGameLevel')
            if current_level == 0:
                current_level = 1
            else:
                current_level += 1

            limit = response_json.get('gameConfig').get('freeSessionGameLevelsMaxCount')
            if limit == 0:
                logger.info(self.log_message("Hurt me game cooldown"))

            while limit != 0:
                json = {"type": "EndGameLevelEvent",
                        "level": int(current_level),
                        "agoClaimed": float(99.75 + randint(1, 5)),
                        "boosted": False,
                        "transactionId": None}

                response1 = await http_client.post(url=f'https://hurt-me-please-server.hexacore.io/game/event',
                                                   json=json)

                if response1.status in (200, 201):
                    logger.info(self.log_message(f"Done {current_level} lvl in Hurt me please"))
                else:
                    logger.info(self.log_message("Hurt me game cooldown"))
                    break
                current_level += 1
                limit -= 1

                await asyncio.sleep(uniform(0.3, 0.6))

            http_client.headers['Authorization'] = old_auth

        except Exception as error:
            log_error(self.log_message(f"Error while play game Hurt me please {error}"))

    async def daily_checkin(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/daily-checkin')
            response_json = await response.json()

            status = response_json.get('is_available')
            next_day = response_json.get('next')

            if status is True:
                json_payload = {"day": next_day}
                response_daily = await http_client.post(url=f'{HEXA_DOMAIN}/api/daily-checkin',
                                                        json=json_payload)
                response_json_daily = await response_daily.json()
                if response_json_daily.get('success') is True:
                    return True, next_day
                else:
                    return False, None
            else:
                return False, None
        except Exception as error:
            log_error(self.log_message(f"Error while daily reward {error}"))

    async def get_tap_passes(self, http_client: CloudflareScraper):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/get-tap-passes')
            response_json = await response.json()
            return response_json
        except Exception as error:
            log_error(self.log_message(f"Error while getting tap passes {error}"))

    async def buy_tap_pass(self, http_client: CloudflareScraper):
        try:
            json = {"name": "7_days"}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/buy-tap-passes', json=json)
            response_json = await response.json()
            if not response_json.get('status') or 'tap pass buying limit reached' in response_json.get('error', "").lower():
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while getting tap passes {error}"))

    async def check_proxy(self, http_client: CloudflareScraper) -> bool:
        proxy_conn = http_client.connector
        if proxy_conn and not hasattr(proxy_conn, '_proxy_host'):
            logger.info(self.log_message(f"Running Proxy-less"))
            return True
        try:
            response = await http_client.get(url='https://ifconfig.me/ip', timeout=aiohttp.ClientTimeout(15))
            logger.info(self.log_message(f"Proxy IP: {await response.text()}"))
            return True
        except Exception as error:
            proxy_url = f"{proxy_conn._proxy_type}://{proxy_conn._proxy_host}:{proxy_conn._proxy_port}"
            log_error(self.log_message(f"Proxy: {proxy_url} | Error: {type(error).__name__}"))
            return False

    async def run(self) -> None:
        random_delay = uniform(1, settings.RANDOM_DELAY_IN_RUN)
        logger.info(self.log_message(f"Bot will start in <ly>{int(random_delay)}s</ly>"))
        await asyncio.sleep(random_delay)

        access_token_created_time = 0
        init_data = None

        token_live_time = randint(3500, 3600)

        proxy_conn = {'connector': ProxyConnector.from_url(self.proxy)} if self.proxy else {}
        async with CloudflareScraper(headers=self.headers, timeout=aiohttp.ClientTimeout(60), **proxy_conn) as http_client:
            while True:
                if not await self.check_proxy(http_client=http_client):
                    logger.warning(self.log_message('Failed to connect to proxy server. Sleep 5 minutes.'))
                    await asyncio.sleep(300)
                    continue

                try:
                    sleep_time = uniform(3500, 3600)
                    if time() - access_token_created_time >= token_live_time or not init_data:
                        init_data = await self.get_tg_web_data()

                        if not init_data:
                            logger.warning(self.log_message('Failed to get webview URL'))
                            await asyncio.sleep(300)
                            continue

                        access_token_created_time = time()

                    auth = await self.register(http_client=http_client, init_data=init_data)
                    if not auth:
                        logger.warning(self.log_message('Failed to authorize. Retrying in 5 minutes'))
                        await asyncio.sleep(300)
                        continue
                        
                    if self.tg_client.is_fist_run:
                        await first_run.append_recurring_session(self.session_name)

                    info = await self.get_balance(http_client=http_client)
                    balance = info.get("balance") or 0
                    logger.info(self.log_message(f'Balance: <lc>{balance}</lc>'))

                    status, next_day = await self.daily_checkin(http_client=http_client)
                    if status is True and next_day is not None:
                        logger.success(self.log_message(f'Daily checkin claimed, streak - {next_day}'))

                    if settings.AUTO_BUY_PASS:
                        data = await self.get_tap_passes(http_client=http_client)
                        if data.get('active_tap_pass') is None and balance >= 1000:
                            status = await self.buy_tap_pass(http_client=http_client)
                            if status:
                                logger.success(self.log_message(f'Bought taps pass for 7 days'))

                    if settings.AUTO_TAP:
                        taps, boosters = await self.get_taps(http_client=http_client)
                        if taps != 0:
                            if boosters != 0:
                                status = await self.use_booster(http_client)
                                if status:
                                    logger.success(self.log_message(f"Used booster"))

                            logger.info(self.log_message(f"<lc>{taps}</lc> taps available, starting clicking"))
                            status = await self.do_taps(http_client=http_client, taps=taps)
                            if status:
                                logger.success(self.log_message(f"Successfully tapped {taps} times"))
                            else:
                                logger.warning(self.log_message(f"Problem with taps"))

                    if settings.AUTO_MISSION:
                        missions = await self.get_missions(http_client=http_client)
                        missions.sort()
                        for mission in missions:
                            status = await self.do_mission(http_client=http_client, id=mission)
                            if status:
                                logger.info(self.log_message(f"Successfully done mission <lc>{mission}</lc>"))
                            await asyncio.sleep(uniform(0.5, 1))

                    if settings.AUTO_LVL_UP:
                        info = await self.get_balance(http_client=http_client)
                        balance = info.get("balance") or 0
                        lvl, available, price, new_lvl = await self.get_level_info(http_client=http_client)
                        if available and price <= balance:
                            if new_lvl:
                                status = await self.level_up(http_client=http_client)
                                if status:
                                    logger.success(self.log_message(f"Successfully level up, now <lc>{new_lvl}</lc> lvl available"))
                            else:
                                logger.info(self.log_message(f"You reached max lvl - 25"))

                    if settings.PLAY_WALK_GAME:
                        status = await self.play_game_1(http_client=http_client)
                        if status:
                            logger.info(self.log_message(f"Successfully played walk game"))
                        else:
                            logger.info(self.log_message(f"Walk game cooldown"))

                    if settings.PLAY_SHOOT_GAME:
                        status = await self.play_game_2(http_client=http_client)
                        if status:
                            logger.info(self.log_message(f"Successfully played shoot game"))
                        else:
                            logger.info(self.log_message(f"Shoot game cooldown"))

                    if settings.PLAY_RPG_GAME:
                        status = await self.play_game_5(http_client=http_client)
                        if status:
                            logger.info(self.log_message(f"Successfully played RPG game"))
                        else:
                            logger.info(self.log_message(f"RPG game cooldown"))

                    if settings.PLAY_DIRTY_JOB_GAME:
                        await self.play_game_3(http_client=http_client)

                    if settings.PLAY_HURTMEPLEASE_GAME:
                        await self.play_game_6(http_client=http_client)

                    logger.info(self.log_message(f"Going sleep 1 hour"))

                    await asyncio.sleep(sleep_time)

                except InvalidSession as error:
                    raise error

                except ConnectionError as error:
                    log_error(self.log_message(f"{error}. Sleep 60 minutes"))
                    await asyncio.sleep(sleep_time)

                except Exception as error:
                    log_error(self.log_message(f"Unknown error: {error}"))
                    await asyncio.sleep(delay=3)
                    continue


async def run_tapper(tg_client: UniversalTelegramClient):
    runner = Tapper(tg_client=tg_client)
    try:
        await runner.run()
    except InvalidSession as e:
        logger.error(runner.log_message(f"Invalid Session: {e}"))
