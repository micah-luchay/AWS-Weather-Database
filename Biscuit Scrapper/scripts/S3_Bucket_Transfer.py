import boto3, os, bs4, time
from bs4 import BeautifulSoup

def classify_hmtl(html_path): # parse out the html file's ingredients to determine biscuit type
    with open(html_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser') # parse out local html file

    classes = ["mm-recipes-structured-ingredients__list-item", "mm-recipes-structured-ingredients__list-item "] # class IDs for list of ingredients
    ingredientsLI = soup.findAll("li", class_=classes) # search the ResultSet this specific class in list items
    biscuitType = None # declare type of biscuit here

    for ingredient in ingredientsLI: # search the ingredients to ascertain type of biscuit
        ingredient = ingredient.text.lower() # convert ResultSet to text for ingredients
        if "buttermilk" in ingredient:
            biscuitType = "buttermilk"
        elif "gravy" in ingredient:
            biscuitType = "gravy"
        else:
            biscuitType = "common_other"
        return biscuitType # return biscuit type

def upload(client, file_path, bucket_name, object_name = None):
    if object_name is None:
        object_name = os.path.basename(file_path) # make object name that of the local file
    try:
        response = client.upload_file(file_path, bucket_name, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_objects(client, bucket_name, file_paths):

    folders = ['buttermilk/', 'common_other/', 'gravy/'] # 3 categories for biscuit types
    for folder in folders:
        # Create a 0-byte object to represent the folder
        client.put_object(Bucket=bucket_name, Key=folder)
    """
    response = client.list_objects_v2(Bucket=bucket_name, Delimiter='/')
    if 'CommonPrefixes' in response:
        print("Folders in bucket:")
        for prefix in response['CommonPrefixes']:
            print(prefix['Prefix'])
    """
    for key in file_paths:
        biscuitType = classify_hmtl(file_paths[key]) # ascertain biscuit type, pass in full path
        object = f"{biscuitType}/{key}"  # folder/object_name
        upload(client, file_paths[key], bucket_name, object) # upload each recipe html page to S3 Bucket

def main(folder_path, bucket_name):
    s3_client = boto3.client('s3')
    paths = {} # file name and full file path here
    for root, dirs, files in os.walk(folder_path): # crawl root folder
        for file in files:
            if os.path.splitext(file)[1] == ".html": # only grab html files
                paths[file] = os.path.join(root, file) # add file name: full file path pair to dictionary

    create_objects(s3_client, bucket_name, paths) # add in objects

main(r"C:\Users\Micah Luchay\Documents\Data Engineering\Biscuit Scrapper\biscuit_spider\Crawled_Pages", "biscuit-recipes")
