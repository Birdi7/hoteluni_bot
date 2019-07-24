### HotelUni_bot 
written with [aiogram](https://github.com/aiogram/aiogram) and [umongo](https://github.com/Scille/umongo)

This bot is able to send reminders about cleanings in he campuses of Innopolis University

#### Running

This project is deployed using [docker-compose](docker_compose).
There is **no mongoDB** configuration in the docker-compose file.
You should use [Atlas](https://www.mongodb.com/cloud/atlas)
and specify running parameters in the environment file (second step), 
or add it on your own.   
 
With docker-compose:
1. Clone the repo with `git clone https://github.com/Birdi7/hoteluni_bot.git`
2. Copy an example environment file with `cp example.env .env`
3. Modify the local environment file named `.env`   
4. Run `docker-compose up -d --build`


[docker_compose]: <https://docs.docker.com/compose/>
