from airflow import DAG
from airflow.providers.http.hooks.http import HttpHook
# So, Airflow basically provides different kinds of Hooks for different different services, like fetching the data from the API, -
#   (Http request) HttpHook will be used!
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task
from airflow.utils.dates import days_ago
import requests
import json


# Latitude and Longitude for the desired location (London in this case)
LATITUDE = '51.5074'
LONGITUDE = '-0.1278'
POSTGRES_CONN_ID = 'postgres_default'  # You can set any connection ID
API_CONN_ID =  'open_meteo_api'        # Connection name

# Basic setup that we require in Airflow:
default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1)
}

## DAG  (Directed Acyclic Graph)
with DAG(dag_id = 'weather_etl_pipeline', #DAG ID
        default_args = default_args,    #default arguments
        schedule_interval = '@daily',   #what interval we need to run this
        catchup = False) as dags:
    
    @task()  # So We've already imported the 'task' at the top, We'll be using this as a Decorator!
    def extract_weather_data():
        """Extract weather data from Open-Meteo API using Airflow connection. """

        # Use HTTP Hook to get the Weather Data / connection from Airflow connection(Just like configuration in Airflow)
        http_hook = HttpHook(http_conn_id = API_CONN_ID, method='GET')  #This connection_id needs to be created in Airflow!

        # Build the API endpoint
        # https://api.open-meteo.com/v1/forecast?latitude=51.5074&longitude=-0.1278&current_weather=true
        endpoint = f'/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true'

        # What is Front-URL? What exactly it is?
            # Without that particular URL, you'll not be able to find out like, where which API we're specificly hitting it right! 
        ## Make the request via the HTTP Hook
        response = http_hook.run(endpoint)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f'Failed to fetch the weather data: {response.status_code}')


    @task()
    def transform_weather_data(weather_data):
        """Transform the extracted weather data."""
        current_weather = weather_data['current_weather']
        transformed_data = {
            'latitude' : LATITUDE,
            'longitude' : LONGITUDE,
            'temperature' : current_weather['temperature'],
            'windspeed' : current_weather['windspeed'],
            'winddirection' : current_weather['winddirection'],
            'weathercode' : current_weather['weathercode'],
        }
        return transformed_data
    
    # Once, we have the transformed data, then now, we have to load it onto the PostgresSQL server! 
    @task()
    def load_weather_data(transformed_data):
        """Load transformed data into PostgreSQL"""
        pg_hook = PostgresHook(postgres_conn_id = POSTGRES_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        #Crate Table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data(
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            windspeed FLOAT,
            winddirection FLOAT,
            weathercode INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """) 

        # Insert transformed data into the table
        cursor.execute("""
        INSERT INTO weather_data(latitude, longitude, temperature, windspeed, winddirection, weathercode)
        VALUES(%s, %s, %s, %s, %s, %s)
        """,(
            transformed_data['latitude'],
            transformed_data['longitude'],
            transformed_data['temperature'],
            transformed_data['windspeed'],
            transformed_data['winddirection'],
            transformed_data['weathercode'],
        ))

        conn.commit()
        conn.close()
    
    ## DAG Workflow - ETL Pipeline:
    weather_data = extract_weather_data()
    transformed_data = transform_weather_data(weather_data)
    load_weather_data(transformed_data)