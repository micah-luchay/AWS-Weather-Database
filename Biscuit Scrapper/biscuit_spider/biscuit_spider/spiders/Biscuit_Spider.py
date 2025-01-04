from pathlib import Path
import scrapy, os
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse, urlunparse

class BiscuitSpider(scrapy.Spider):
    name = "Biscuit_Spider" # name of subclass, use this in cmd line to run this code "scrapy crawl Biscuit_Spider"
    currentURL = "https://www.allrecipes.com/recipe/174386/homemade-biscuit-mix/" # start with a url first
    crawledList = [] # stores a list of crawled URLs here to avoid crawling same page
    foodList = None # store foods here to search for to break crawling loop
    linkList = set() # store list of links here, use a set to avoid duplicates

    def create_folder(self, folderName): # house the crawling results in a unique folder
        folderPath = os.path.join("Crawled_Pages", folderName)
        os.makedirs(folderPath, exist_ok=True)
        return folderPath

    def parse_url(self, url): # remove fragments of urls and only return the url of page
        urlParsed = urlparse(url)  # parse url of response into components
        urlCleansed = urlunparse(urlParsed._replace(fragment=""))  # reconstruct url without fragment
        return urlCleansed

    def extract_links(self, response): # extract links from page
        link_extractor = LinkExtractor(allow=[r"/recipe/", "-recipe-"], allow_domains=["allrecipes.com"], tags=['a'],
                                   attrs=['href',
                                          'data-url'])  # create instance of a link extractor that extracts links from allrecipes.com
        links = link_extractor.extract_links(response)  # pass in response into link extractor, return links on html page
        linkList = [link.url for link in links]
        return linkList

    def change_currentURL(self): # handles redirects/errors to avoid loops
        if len(self.linkList) == 0: # ran out of links extracted, search for new links
            popFood = self.foodList.pop(0)  # pop the first food in list, remove from list
            self.currentURL = f"https://www.allrecipes.com/search?q={popFood}"  # generate a random search of food on website
            self.log(f"Need to search for new URLs on homepage: {self.currentURL}")
        else:
            randomLink = self.linkList.pop() # pop element from set
            self.currentURL = self.parse_url(randomLink) # set current link to be popped element
            self.crawledList.append(randomLink) # add to crawled list to avoid duplicate crawling
            self.log(f"Changed current URL to: {randomLink}")

    def start_requests(self): # initially makes the first request
        urls = [self.currentURL]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)

    def handle_error(self, failure):
        # Handle errors like 404, redirect, etc.
        self.logger.error(f"Request failed with error: {failure.value}")
        self.change_currentURL()  # Change the current URL

        yield scrapy.Request(url=self.currentURL, callback=self.parse, errback=self.handle_error, dont_filter=True) # Retry with the new URL

    def parse(self, response):
        responseURL = response.url

        if "Redirect" in responseURL or "redirect" in responseURL: # response was a redirect URL, need to change it otherwise a loop will occur
            self.change_currentURL() # change current URL
            recipe_title = None # nothing usable on redirect, declare empty variables
            links = set()

        elif "search?q=" not in self.currentURL: # if not on the homepage, extract the recipe name
            recipe_title = response.css('.article-heading::text').getall()[0] # there are 2 classes associated with recipe name, use the first
            page_name = f"{recipe_title}.html" # create html file name
            links = self.extract_links(response) # extract links on page to continue crawling

        elif "search?q=" in self.currentURL: # extract links only if on homepage, don't create file/recipe name
            recipe_title = None
            links = self.extract_links(response) # extract links to continue crawling

        links = set(links) # transform links into a set to remove duplicates
        self.linkList.update(links) # add all the usable links from page to class variable
        self.change_currentURL() # change the current URL to something else

        if responseURL == self.currentURL: # encountered a looping crawl, need to mix it up
            foods = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape", "Honeydew", "Kiwi", "Lemon", "Mango", "Nectarine", "Orange", "Papaya", "Peach", "Pear", "Plum", "Pomegranate", "Raspberry", "Strawberry", "Asparagus", "Beetroot", "Broccoli", "Cabbage", "Carrot", "Cauliflower", "Celery", "Cucumber", "Eggplant", "Garlic",
                     "Kale", "Lettuce", "Mushroom", "Onion", "Peas", "Pepper (Bell)", "Potato", "Spinach", "Sweet Potato", "Zucchini", "Bagel", "Baguette", "Barley", "Brown Rice", "Cornbread", "Couscous", "Multigrain Bread", "Oatmeal", "Quinoa", "Rye Bread","Bacon", "Beef", "Chicken", "Duck", "Eggs", "Ham", "Lamb", "Pork", "Salmon", "Shrimp",
                     "Butter", "Cheddar Cheese", "Cream Cheese", "Cottage Cheese", "Feta", "Greek Yogurt", "Ice Cream", "Milk", "Mozzarella", "Yogurt","Brownie", "Cake", "Candy", "Chocolate", "Cookie", "Croissant", "Doughnut", "Granola Bar", "Muffin", "Popcorn", "Burrito", "Dim Sum", "Falafel", "Gnocchi", "Kimchi", "Pad Thai", "Paella", "Pizza", "Ramen", "Tacos"
                    ]
            if not self.foodList: # to avoid having to run this for loop every time
                foodsFormatted = [food.replace(" ", "%20") for food in foods] # make html format compliant, replace spaces with %20
                self.foodList = foodsFormatted
            self.change_currentURL() # change current URL

        if recipe_title and "biscuit" in recipe_title.lower(): # biscuit is in recipe name, store it to a file!!!!
            folderPath = self.create_folder(recipe_title)  # call the self function to create the folder to house results
            with open(os.path.join(folderPath, page_name), "wb") as file: # write out the html file
                file.write(response.body)
            with open(os.path.join(folderPath, "URL.txt"), "w") as file: # write out txt file to document url
                file.write(responseURL)

            self.log(f"Biscuit is crawled: {responseURL}")

        else:
            self.log(f"No biscuit is crawled")

        self.log(self.currentURL)
        self.log(responseURL)

        yield scrapy.Request(url=self.currentURL, callback=self.parse, dont_filter=True, errback=self.handle_error) # recursion, keep sending a request to the website to continue crawling
        # callback continues in successful retrieval, errback handles errors