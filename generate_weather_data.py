import sqlalchemy, requests, random, urllib, json, time, datetime, boto3, re
from sqlalchemy import create_engine, Table, Column, Integer, Float, DateTime, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import MetaData, URL
from zoneinfo import ZoneInfo

"""# Connect to Database"""

connectionURL = URL.create(
    "postgresql+psycopg2",
    username = "REDACTED",
    password = "REDACTED", #getpass.getpass("Password: "),
    host = 'REDACTED',
    database = 'postgres',
    port = 'REDACTED'
)

print(connectionURL)

"""# Create Session and create Base class"""

engine = create_engine(connectionURL)
Session = sessionmaker(bind=engine) # define a session, which is used to interact with the database specified
session = Session() # create the session
Base = declarative_base() # Base class keeps track of the tables you inherit from here

"""# Define a Table"""

def create_weather_table(tableName):

  class Weather_Data(Base): # inherited from Base
    __tablename__ = tableName # Table name in AWS database, make it dynamic

    id = Column(Integer, primary_key = True, autoincrement = True)
    date = Column(DateTime)
    temperature = Column(Integer)
    precipitation = Column(Float)
    humidity = Column(Float)
    windspeed = Column(Integer)
    url = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)

    def __repr__(self): # string representation of the object
      return f"Weather_Data(date={self.date}, temperature={self.temperature}, precipitation={self.precipitation}, humidity = {self.humidity}, windspeed = {self.windspeed}, url = {self.url}, latitude = {self.latitude}, longitude = {self.longitude})"

  return Weather_Data # return the created class

def create_error_table(tableName):

  class Error_Log(Base):
    __tablename__ = tableName

    id = Column(Integer, primary_key= True, autoincrement= True)
    date = Column(DateTime)
    url = Column(String)
    error = Column(String)

    def __repr__(self):
      return f"Error_Log(error={self.error}, url={self.url})"
    
  return Error_Log


"""# Send Request To Server"""

def send_request(request):
  response = urllib.request.urlopen(request)
  data = json.load(response) # convert the response to json format
  #dataFormated = json.dumps(data, indent = 4)
  forecastHourlyAPI = data['properties']['forecastHourly'] # grab the forecast api link of the closest weather station

  response = urllib.request.urlopen(forecastHourlyAPI)
  data = json.load(response)

  keyName = str(re.split("[/,]", request)[-1]) + "_" + str(re.split("[/,]", request)[-2]) # gather lat/long from request
  
  store_bucket("weather-api-response", keyName, json.dumps(data)) # store response in bucket
  
  startTime = data['properties']['periods'][1]['startTime'] # time of weather observation
  temp = data['properties']['periods'][1]['temperature'] # temp of weather observation
  probabilityRain = data['properties']['periods'][1]['probabilityOfPrecipitation']['value'] # grab probability of rain
  humidity = data['properties']['periods'][1]['relativeHumidity']['value'] # grab humidity
  windspeed = data['properties']['periods'][1]['windSpeed'].split(' ')[0] # grab windspeed

  return [startTime, temp, probabilityRain, humidity, windspeed, forecastHourlyAPI]

"""# Grab Table Name"""

def get_table(TableType): # use this function to either return the current table or create a new table at midnight
  metadata = MetaData() # create MetaData object, which is a collection of table objects and schema constucts
  metadata.reflect(bind=engine) # load the schema, including table names of sql server, specify the connection

  tables = metadata.tables.keys()  # grab the table names from metadata
  current_time = datetime.datetime.now(ZoneInfo("America/New_York")) # use local time zone for Eastern Coast

  match TableType: # determine what table to create
    case "Weather Table":
      currentTable = f"weatherdata_{current_time.year}_{current_time.month}_{current_time.day}"
    case "Error Log":
      currentTable = f"errorlog_{current_time.year}_{current_time.month}_{current_time.day}"

  firstWord = currentTable.split("_")[0] # grab first word from table name
  tableDict = {"weatherdata": create_weather_table, "errorlog": create_error_table} # create dispatch table to determine what table to create

  if currentTable in tables: # table name found in database, between 00:00 and 23:59
    BaseDB = automap_base() # reflect or read the existing database
    BaseDB.prepare(engine, reflect=True) # Reflect/read the tables from the database
    return BaseDB.classes[currentTable] # return the table as a ORM

  elif current_time.hour == 0 and current_time.minute == 0: # at midnight, create new table to store weather data/error log for the day
    #newTable = create_weather_table(currentTable) # create new class with the table name
    newTable = tableDict[firstWord](currentTable)
    Base.metadata.create_all(engine) # create the tables in the SQL server by checking all tables associated with the Base class
    return newTable # return the new table as an object

  elif currentTable not in tables: # use this to create a table for first time running code, only if the first two conditions aren't met
    #newTable = create_weather_table(currentTable)
    newTable = tableDict[firstWord](currentTable)
    Base.metadata.create_all(engine) # create the tables in the SQL server by checking all tables associated with the Base class
    return newTable

def store_bucket(bucketName, dataName, data):
  s3 = boto3.resource('s3') # call resource
  currentTime = datetime.datetime.now(ZoneInfo("America/New_York")) # use local time zone for Eastern Coast
  keyObj = f"{currentTime.year}_{currentTime.month}_{currentTime.day}__{currentTime.hour}-{currentTime.minute}/{dataName}.json" # store objects in folder

  try:
    bucket = s3.Bucket(bucketName)
    response = bucket.put_object(Key = keyObj, Body = data) # doc https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html
    print(f"{response}")

  except Exception as e:
    print(e)

def send_weather_request(event, context):
  #while True: # continuously run

  longitude = random.uniform(-122, -81)
  latitude = random.uniform(30, 49)
  request = f'https://api.weather.gov/points/{latitude},{longitude}'

  try:
      weatherInfo = send_request(request) # try to send a request to the server
      weatherInfo = weatherInfo + [latitude, longitude] # add xy location to array
      tableName = get_table("Weather Table") # grab current table in database or make it
      weatherPoint = tableName(date = weatherInfo[0], # populate the table
                              temperature = weatherInfo[1],
                              precipitation = weatherInfo[2],
                              humidity = weatherInfo[3],
                              windspeed = weatherInfo[4],
                              url = weatherInfo[5],
                              latitude = weatherInfo[6],
                              longitude = weatherInfo[7])
      session.add(weatherPoint) # add the instance to the database
      session.commit()
      print(f"{weatherPoint} added successfully")

  except Exception as e:
      tableName = get_table("Error Log") # grab current table in database or make it
      errorLog = tableName(date = datetime.datetime.now(ZoneInfo("America/New_York")), # use local time zone for Eastern Coast
                          url = request,
                          error = str(e))
      session.add(errorLog)
      session.commit()
      print(f"Error parsing request. {errorLog} logged.")
