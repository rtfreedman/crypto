docker-compose up -d
source bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
source .creds/setdev.sh
python manage.py collectstatic --no-input
python manage.py runserver 0.0.0.0:8000
unset STATIC_ROOT CBA_API_KEY CBA_API_SECRET CRYPTO_DB CRYPTO_DB_USER CRYPTO_DB_PASS CRYPTO_DB_HOST CRYPTO_DB_PORT