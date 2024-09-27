import aiohttp
import asyncio
import fasteners
import os
import random
from urllib.parse import unquote
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from time import time

from telethon import TelegramClient
from telethon.errors import *
from telethon.types import InputUser, InputBotAppShortName, InputPeerUser
from telethon.functions import messages, contacts

from .agents import generate_random_user_agent
from .headers import *
from bot.config import settings
from bot.utils import logger, log_error, proxy_utils, config_utils, CONFIG_PATH
from bot.exceptions import InvalidSession

HEXA_DOMAIN = "https://ago-api.hexacore.io"


class Tapper:
    def __init__(self, tg_client: TelegramClient):
        self.session_name, _ = os.path.splitext(os.path.basename(tg_client.session.filename))
        self.tg_client = tg_client
        self.config = config_utils.get_session_config(self.session_name, CONFIG_PATH)
        self.proxy = self.config.get('proxy', None)
        self.lock = fasteners.InterProcessLock(os.path.join(os.path.dirname(CONFIG_PATH), 'lock_files',  f"{self.session_name}.lock"))
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.time_end = 0
        self.headers = headers
        self.headers['User-Agent'] = self.check_user_agent()
        self.headers.update(**get_sec_ch_ua(self.headers.get('User-Agent', '')))

        self._webview_data = None

    def log_message(self, message) -> str:
        return f"<light-yellow>{self.session_name}</light-yellow> | {message}"

    def check_user_agent(self):
        user_agent = self.config.get('user_agent')
        if not user_agent:
            user_agent = generate_random_user_agent()
            self.config['user_agent'] = user_agent
            config_utils.update_session_config_in_file(self.session_name, self.config, CONFIG_PATH)

        return user_agent

    async def get_tg_web_data(self) -> [str | None, str | None]:
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            proxy_dict = proxy_utils.to_telethon_proxy(proxy)
        else:
            proxy_dict = None
        self.tg_client.set_proxy(proxy_dict)

        data = None, None
        with self.lock:
            async with self.tg_client as client:
                if not self._webview_data:
                    while True:
                        try:
                            peer = await client.get_input_entity('HexacoinBot')
                            input_bot_app = InputBotAppShortName(bot_id=peer, short_name="wallet")
                            self._webview_data = {'peer': peer, 'app': input_bot_app}
                            break
                        except FloodWaitError as fl:
                            fls = fl.seconds

                            logger.warning(self.log_message(f"FloodWait {fl}"))
                            logger.info(self.log_message(f"Sleep {fls}s"))
                            await asyncio.sleep(fls + 3)

                ref_id = settings.REF_ID if random.randint(0, 100) <= 85 else "525256526"

                web_view = await client(messages.RequestAppWebViewRequest(
                    **self._webview_data,
                    platform='android',
                    write_allowed=True,
                    start_param=ref_id
                ))

                auth_url = web_view.url
                tg_web_data = unquote(
                    string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

                try:
                    information = await client.get_me()
                    self.user_id = information.id
                    self.first_name = information.first_name or ''
                    self.last_name = information.last_name or ''
                    self.username = information.username or ''
                except Exception as e:
                    print(e)

                self.fullname = f'{self.first_name} {self.last_name}'.strip()

                data = tg_web_data, ref_id

        return data

    async def auth(self, http_client: aiohttp.ClientSession, init_data):
        try:
            json = {"data": init_data}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/app-auth', json=json)
            response.raise_for_status()
            response_json = await response.json()
            return response_json.get('token')
        except Exception as error:
            log_error(self.log_message(f"Error while auth {error}"))
            return

    async def register(self, http_client: aiohttp.ClientSession, ref_id, init_data):
        try:
            json = {}

            if not http_client.headers.get('Authorization'):
                auth_token = await self.auth(http_client=http_client, init_data=init_data)
                if not auth_token:
                    raise ConnectionError('Failed to get auth token')
                http_client.headers['Authorization'] = auth_token

            if self.username != '':
                json = {
                    "user_id": int(self.user_id),  # Ensure user_id is a string
                    "fullname": f"{str(self.fullname)}",
                    "username": f"{str(self.username)}",
                    "referer_id": f"{str(ref_id)}"
                }
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
                    log_error(self.log_message(f"Something wrong with register! {response.status}"))
                    return False
            else:
                log_error(self.log_message(f"Error while register, please add username to telegram account"))
                return False
        except ConnectionError as error:
            raise error
        except Exception as error:
            log_error(self.log_message(f"Error while register {error}"))
            return False

    async def get_taps(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/available-taps')
            response_json = await response.json()
            taps = response_json.get('available_taps')
            boosters = response_json.get('available_boosters')
            return taps, boosters
        except Exception as error:
            log_error(self.log_message(f"Error while get taps {error}"))

    async def get_balance(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/balance/{self.user_id}')
            response_json = await response.json()
            return response_json
        except Exception as error:
            log_error(self.log_message(f"Error while get balance {error}"))

    async def do_taps(self, http_client: aiohttp.ClientSession, taps):
        try:
            json = {"taps": taps}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/mining-complete', json=json)
            response_json = await response.json()

            if not response_json.get('success'):
                return False

            return True

        except Exception as error:
            log_error(self.log_message(f"Error while do taps {error}"))

    async def use_booster(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.post(f"{HEXA_DOMAIN}/api/activate-boosters")
            resp_json = await response.json()
            success = resp_json.get('success')
            return success
        except Exception as error:
            log_error(self.log_message(f"Error while trying to use buster - {error}"))

    async def get_missions(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/missions')
            response_json = await response.json()
            incomplete_mission_ids = [mission['id'] for mission in response_json if (not mission['isCompleted']
                                                                                     and mission['autocomplete'])]

            return incomplete_mission_ids
        except Exception as error:
            log_error(self.log_message(f"Error while get missions {error}"))

    async def do_mission(self, http_client: aiohttp.ClientSession, id):
        try:
            json = {'missionId': id}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/mission-complete', json=json)
            response_json = await response.json()
            if not response_json.get('success'):
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while doing missions {error}"))

    async def get_level_info(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/level')
            response_json = await response.json()
            lvl = response_json.get('lvl')
            upgrade_available = response_json.get('upgrade_available', None)
            upgrade_price = response_json.get('upgrade_price', None)
            new_lvl = response_json.get('next_lvl', None)
            return lvl, upgrade_available, upgrade_price, new_lvl
        except Exception as error:
            log_error(self.log_message(f"Error while get level {error}"))

    async def level_up(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/upgrade-level')
            response_json = await response.json()
            if not response_json.get('success'):
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while up lvl {error}"))

    async def play_game_1(self, http_client: aiohttp.ClientSession):
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

    async def play_game_2(self, http_client: aiohttp.ClientSession):
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

    async def play_game_3(self, http_client: aiohttp.ClientSession):
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

                await asyncio.sleep(random.uniform(1, 1.5))

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

                await asyncio.sleep(random.uniform(0.5, 1))

            http_client.headers['Authorization'] = old_auth
        except Exception as error:
            log_error(self.log_message(f"Error while play game 3 {error}"))

    async def play_game_5(self, http_client: aiohttp.ClientSession):
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

    async def play_game_6(self, http_client: aiohttp.ClientSession):
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
                        "agoClaimed": float(99.75 + random.randint(1, 5)),
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

                await asyncio.sleep(random.uniform(0.3, 0.6))

            http_client.headers['Authorization'] = old_auth

        except Exception as error:
            log_error(self.log_message(f"Error while play game Hurt me please {error}"))

    async def daily_checkin(self, http_client: aiohttp.ClientSession):
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

    async def get_tap_passes(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get(url=f'{HEXA_DOMAIN}/api/get-tap-passes')
            response_json = await response.json()
            return response_json
        except Exception as error:
            log_error(self.log_message(f"Error while getting tap passes {error}"))

    async def buy_tap_pass(self, http_client: aiohttp.ClientSession):
        try:
            json = {"name": "7_days"}
            response = await http_client.post(url=f'{HEXA_DOMAIN}/api/buy-tap-passes', json=json)
            response_json = await response.json()
            if response_json.get('status') is False:
                return False
            return True
        except Exception as error:
            log_error(self.log_message(f"Error while getting tap passes {error}"))

    async def check_proxy(self, http_client: aiohttp.ClientSession) -> bool:
        proxy_conn = http_client._connector
        try:
            response = await http_client.get(url='https://ifconfig.me/ip', timeout=aiohttp.ClientTimeout(15))
            logger.info(self.log_message(f"Proxy IP: {await response.text()}"))
            return True
        except Exception as error:
            proxy_url = f"{proxy_conn._proxy_type}://{proxy_conn._proxy_host}:{proxy_conn._proxy_port}"
            log_error(self.log_message(f"Proxy: {proxy_url} | Error: {type(error).__name__}"))
            return False

    async def run(self) -> None:
        random_delay = random.randint(1, settings.RANDOM_DELAY_IN_RUN)
        logger.info(self.log_message(f"Bot will start in <ly>{random_delay}s</ly>"))
        await asyncio.sleep(random_delay)

        access_token_created_time = 0
        init_data = None

        token_live_time = random.randint(3500, 3600)

        proxy_conn = {'connector': ProxyConnector.from_url(self.proxy)} if self.proxy else {}
        async with CloudflareScraper(headers=self.headers, timeout=aiohttp.ClientTimeout(60), **proxy_conn) as http_client:
            while True:
                if not await self.check_proxy(http_client=http_client):
                    logger.warning(self.log_message('Failed to connect to proxy server. Sleep 5 minutes.'))
                    await asyncio.sleep(300)
                    continue

                try:
                    sleep_time = random.uniform(3500, 3600)
                    if time() - access_token_created_time >= token_live_time:
                        init_data, ref_id = await self.get_tg_web_data()

                        if not init_data:
                            raise InvalidSession('Failed to get webview URL')

                    access_token_created_time = time()

                    await self.register(http_client=http_client, init_data=init_data, ref_id=ref_id)

                    info = await self.get_balance(http_client=http_client)
                    balance = info.get("balance") or 0
                    logger.info(self.log_message(f'Balance: {balance}'))

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

                            logger.info(self.log_message(f"{taps} taps available, starting clicking"))
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
                                logger.info(self.log_message(f"Successfully done mission {mission}"))
                            await asyncio.sleep(random.uniform(0.5, 1))

                    if settings.AUTO_LVL_UP:
                        info = await self.get_balance(http_client=http_client)
                        balance = info.get("balance") or 0
                        lvl, available, price, new_lvl = await self.get_level_info(http_client=http_client)
                        if available and price <= balance:
                            if new_lvl:
                                status = await self.level_up(http_client=http_client)
                                if status:
                                    logger.success(self.log_message(f"Successfully level up, now {new_lvl} lvl available"))
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


async def run_tapper(tg_client: TelegramClient):
    runner = Tapper(tg_client=tg_client)
    try:
        await runner.run()
    except InvalidSession as e:
        logger.error(runner.log_message(f"Invalid Session: {e}"))
