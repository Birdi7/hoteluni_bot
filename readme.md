### HotelUni_bot 
written with [aiogram](https://github.com/aiogram/aiogram) and [umongo](https://github.com/Scille/umongo). Basic structure was taken from [this](https://github.com/Birdi7/Template-Telegram-bot) template.

~~**Running instance: [@hoteluni_bot](t.me/hoteluni_bot).**~~
**Currently down**


This bot can send reminders about cleanings in the campuses of the Innopolis University.

#### Dependencies
To run this bot correctly, you need a MongoDB cluster and a Redis server running. The first one is used for the user data, and the second one contains FSM data of users. [APScheduler](https://github.com/agronholm/apscheduler) is used for scheduling events. See [requirements.txt](requirements.txt) for more information.

#### Running

This project is deployed using [docker-compose](docker_compose).
There is **no mongoDB** configuration in the docker-compose file.
You can use [Atlas](https://www.mongodb.com/cloud/atlas)
and specify running parameters in the environment file (second step), 
or add it on your own.   
 
With docker-compose:
1. Clone the repo with `git clone https://github.com/Birdi7/hoteluni_bot.git`
2. Copy an example environment file with `cp example.env .env`
3. Modify the local environment file named `.env`   
4. Run `docker-compose up -d --build`


[docker_compose]: <https://docs.docker.com/compose/>
