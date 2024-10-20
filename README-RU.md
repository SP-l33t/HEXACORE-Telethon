[![Static Badge](https://img.shields.io/badge/Телеграм-Наш_канал-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_coding)

[![Static Badge](https://img.shields.io/badge/Телеграм-Наш_чат-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_codding_chat)

[![Static Badge](https://img.shields.io/badge/Телеграм-Ссылка_на_бота-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/HexacoinBot/wallet?startapp=737844465)

## Рекомендация перед использованием

# 🔥🔥 Используйте PYTHON версии 3.10 🔥🔥

> 🇪🇳 README in english available [here](README-EN)

## Функционал  
|               Функционал               | Поддерживается |
|:--------------------------------------:|:--------------:|
|            Многопоточность             |       ✅        | 
|        Привязка прокси к сессии        |       ✅        | 
|    Авто тапанье куба в главном меню    |       ✅        |
|         Авто игра в игры бота          |       ✅        |
|         Авто выполнение миссий         |       ✅        |
|    Авто реферальство ваших твинков     |       ✅        |
| Поддержка telethon И pyrogram .session |       ✅        |

_Скрипт осуществляет поиск файлов сессий в следующих папках:_
* /sessions
* /sessions/pyrogram
* /session/telethon


## [Настройки](https://github.com/HiddenCodeDevs/HEXACOREbot/blob/main/.env-example/)
|         Настройки          |                                                                                                                              Описание                                                                                                                               |
|:--------------------------:|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|
|   **API_ID / API_HASH**    |                                                                                         Данные платформы, с которой будет запущена сессия Telegram (по умолчанию - android)                                                                                         |
|   **GLOBAL_CONFIG_PATH**   | Определяет глобальный путь для accounts_config, proxies, sessions. <br/>Укажите абсолютный путь или используйте переменную окружения (по умолчанию - переменная окружения: **TG_FARM**)<br/> Если переменной окружения не существует, использует директорию скрипта |
|        **FIX_CERT**        |                                                                                              Попытаться исправить ошибку SSLCertVerificationError ( True / **False** )                                                                                              |
|        **AUTO_TAP**        |                                                                                                       Авто тапанье куба в главном меню (по умолчанию - True)                                                                                                        |
|      **AUTO_MISSION**      |                                                                                                       Авто выполнение доступных миссий (по умолчанию - True)                                                                                                        |
|      **AUTO_LVL_UP**       |                                                                                                         Авто улучшение уровня в боте (по умолчанию - True)                                                                                                          |
|     **PLAY_WALK_GAME**     |                                                                                               Авто получение награды в Hexacore Gaming Universe (по умолчанию - True)                                                                                               |
|    **PLAY_SHOOT_GAME**     |                                                                                                      Авто получение награды в Pin Bullet (по умолчанию - True)                                                                                                      |
|     **PLAY_RPG_GAME**      |                                                                                                         Авто получение награды в Pals (по умолчанию - True)                                                                                                         |
|  **PLAY_DIRTY_JOB_GAME**   |                                                                                                      Авто получение награды в Dirty Job (по умолчанию - True)                                                                                                       |
| **PLAY_HURTMEPLEASE_GAME** |                                                                                                    Авто получение награды в Hurt me please (по умолчанию - True)                                                                                                    |
|     **AUTO_BUY_PASS**      |                                                                                                   Авто покупка прибыльной подписки на клики (по умолчанию - True)                                                                                                   |
|  **RANDOM_DELAY_IN_RUN**   |                                                                        Задержка для старта каждой сессии от 1 до установленного значения (по умолчанию : **30**, задержка в интервале 1..30)                                                                        |
|         **REF_ID**         |                                                                                    Автоматически рефералит ваших твинков (по умолчанию - Нету, введите сюда ваш телеграмм айди)                                                                                     |
|   **SESSIONS_PER_PROXY**   |                                                                                           Количество сессий, которые могут использовать один прокси (По умолчанию **1** )                                                                                           |
|  **USE_PROXY_FROM_FILE**   |                                                                                             Использовать ли прокси из файла `bot/config/proxies.txt` (**True** / False)                                                                                             |
| **DISABLE_PROXY_REPLACE**  |                                                                                   Отключить автоматическую проверку и замену нерабочих прокси перед стартом ( True / **False** )                                                                                    |
|     **DEVICE_PARAMS**      |                                                                                  Вводить параметры устройства, чтобы сделать сессию более похожую, на реальную  (True / **False**)                                                                                  |
|     **DEBUG_LOGGING**      |                                                                                               Включить логирование трейсбэков ошибок в папку /logs (True / **False**)                                                                                               |

## Быстрый старт 📚

Для быстрой установки и последующего запуска - запустите файл run.bat на Windows или run.sh на Линукс

## Предварительные условия
Прежде чем начать, убедитесь, что у вас установлено следующее:
- [Python](https://www.python.org/downloads/) **версии 3.10**

## Получение API ключей
1. Перейдите на сайт [my.telegram.org](https://my.telegram.org) и войдите в систему, используя свой номер телефона.
2. Выберите **"API development tools"** и заполните форму для регистрации нового приложения.
3. Запишите `API_ID` и `API_HASH` в файле `.env`, предоставленные после регистрации вашего приложения.

## Установка
Вы можете скачать [**Репозиторий**](https://github.com/HiddenCodeDevs/HEXACOREbot) клонированием на вашу систему и установкой необходимых зависимостей:
```shell
git clone https://github.com/HiddenCodeDevs/HEXACOREbot.git
cd HEXACOREbot
```

Затем для автоматической установки введите:

Windows:
```shell
run.bat
```

Linux:
```shell
run.sh
```

# Linux ручная установка
```shell
sudo sh install.sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env-example .env
nano .env  # Здесь вы обязательно должны указать ваши API_ID и API_HASH , остальное берется по умолчанию
python3 main.py
```

Также для быстрого запуска вы можете использовать аргументы, например:
```shell
~/HEXACOREbot >>> python3 main.py --action (1/2)
# Or
~/HEXACOREbot >>> python3 main.py -a (1/2)

# 1 - Запускает кликер
# 2 - Создает сессию
```


# Windows ручная установка
```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env-example .env
# Указываете ваши API_ID и API_HASH, остальное берется по умолчанию
python main.py
```

Также для быстрого запуска вы можете использовать аргументы, например:
```shell
~/HEXACOREbot >>> python main.py --action (1/2)
# Или
~/HEXACOREbot >>> python main.py -a (1/2)

# 1 - Запускает кликер
# 2 - Создает сессию
```




### Контакты

Для поддержки или вопросов, свяжитесь со мной в Telegram:

[![Static Badge](https://img.shields.io/badge/Телеграм-автор_бота-link?style=for-the-badge&logo=telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/ВАШЮЗЕРНЕЙМВТГ)
