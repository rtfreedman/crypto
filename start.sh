docker-compose up -d
source bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
STATIC_ROOT=`cat .creds/static` python manage.py collectstatic --no-input
STATIC_ROOT=`cat .creds/static` CBAAPIKEY=`cat .creds/key` CBAAPISECRET=`cat .creds/secret` python manage.py runserver 0.0.0.0:8000