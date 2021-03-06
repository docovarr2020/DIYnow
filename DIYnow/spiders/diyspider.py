# https://blog.siliconstraits.vn/building-web-crawler-scrapy/
# http://stackoverflow.com/questions/11128596/scrapy-crawlspider-how-to-access-item-across-different-levels-of-parsing
from scrapy.spiders import Spider
from DIYnow.items import DiynowItem
from scrapy.http import Request
import random

# number of projects to parse from each site
NUM_MAKEZINE_PROJECTS = 3
NUM_INSTRUCTABLES_PROJECTS = 3
NUM_LIFEHACKER_PROJECTS = 3

# number of recent lifehacker DIY projects to potentially reference (here last 5000)
LIFEHACKER_RANGE = 5000

# defines for project categories we exclude in Makezine search
MAKEZINE_EDUCATION = 3
MAKER_NEWS = 5
UNCATEGORIZED = 8
PAGE = 10

class ProjectSpider(Spider):
    """Our main spider, used to randomly parse 3 DIY sites for projects"""
    # name of the spider, used to launch the spider
    name = "Projects"

    # a list of URLs that the crawler will start at
    start_urls = ["http://makezine.com/sitemap/"]

    # starting the chain of requests
    def parse(self, response):
        """the default callback method (spider will call parse from the start_url)
           in this case, chooses categories from Makezine's sitemap """

        # list of html elements with this xpath (the project categories)
        categories = response.xpath('//li[contains(@class, "title")]/a')

        # ensure this list is not empty (site format is same)
        if categories.extract_first() is not None:
            for i in range(NUM_MAKEZINE_PROJECTS):
                # generate a random number to select a random project category
                # however, exclude certain categories (not diy project related)
                rand_num = -1
                while(rand_num == -1 or rand_num == MAKEZINE_EDUCATION or
                        rand_num == MAKER_NEWS or rand_num == UNCATEGORIZED or
                        rand_num == PAGE):

                    rand_num = random.randrange(0, len(categories))
                # join our current url with the next random category
                category = response.urljoin(
                    # get a list of project cateogry urls from the sitemap
                    (categories.xpath('@href').extract())
                    # choose random project category url from list
                    [rand_num])

                # passing control over to parse_makezine_projects
                # dont filter set to true to allow spider to crawl same category twice
                yield Request(category, callback = self.parse_makezine_projects, dont_filter = True)

            # http://stackoverflow.com/questions/17560575/using-scrapy-to-extract-information-from-different-sites
            # passing request to next site, instructables, to get more projects
            yield Request(url="http://www.instructables.com/sitemap/instructables/", callback=self.parse_instructables_categories)

    def parse_makezine_projects(self, response):
        """ when given a Makezine project page, extract the wanted elements"""

        # list of html elements with xpath that leads to project link
        projects = response.xpath('//ul[contains(@class, "sitemap_links")]/li/a')

        # declare instance of a DiynowItem and start to fill in fields
        item = DiynowItem()
        # process_info will fill in the project title and url
        process_info(projects, item)
        # find the url for the page of the random project of "item"
        project_page = response.urljoin(item["url"])

        # parse that random project page (with parse_project_page()), and update item's image_url field
        request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
        request.meta["item"] = item

        # return back to parse method, thus completing project parse and adding to json file
        return request

    def parse_instructables_categories(self, response):
        """ like parse, with different xpath and restrictions """

        categories = response.xpath('//ul[contains(@class, "main-listing")]/li/a')
        # ensure this list is not empty (site format is same)
        if categories.extract_first() is not None:
            for i in range(NUM_INSTRUCTABLES_PROJECTS):

                # join our current url with the next random category
                category = response.urljoin(
                    # get a list of project cateogry urls from the sitemap
                    (categories.xpath('@href').extract())
                    # choose random project category url from list
                    [random.randrange(0, len(categories))])

                # passing control over to parse_instructables_projects
                # dont filter set to true to allow spider to crawl same category twice
                yield Request(category, callback = self.parse_instructables_projects, dont_filter = True)

            # passing request to next site at a random diy category page
            rand_num = random.randrange(0, LIFEHACKER_RANGE)
            # pass control to parse_lifehacker_projects at a random index page
            yield Request(url="http://lifehacker.com/tag/diy?startIndex=" + str(rand_num), callback=self.parse_lifehacker_projects)

    def parse_instructables_projects(self, response):
        """ when given an instructables project page, extract wanted elements"""

        # list of html elements with xpath that leads to project link
        projects = response.xpath('//ul[contains(@class, "main-listing")]/li/a')

        # declare instance of a DiynowItem and start to fill in fields
        item = DiynowItem()
        process_info(projects, item)
        # find the url for the page of the random project of "item"
        project_page = response.urljoin(item["url"])

        # parse that random project page (with parse_project_page()), and update item's image_url field
        request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
        request.meta["item"] = item

        # end the chain of requests
        return request

    def parse_lifehacker_projects(self, response):
        # list of html elements with xpath that leads to project link
        projects = response.xpath('//h1[contains(@class, "headline entry-title js_entry-title")]/a')

        if projects.extract_first() is not None:
            for i in range(NUM_LIFEHACKER_PROJECTS):
                # declare instance of a DiynowItem and start to fill in fields
                item = DiynowItem()
                process_info(projects, item)

                # find the url for the page of the random project of "item"
                project_page = response.urljoin(item["url"])

                # parse that random project page (with parse_project_page()), and update item's image_url field
                request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
                request.meta["item"] = item

                yield request

    def parse_project_page(self, response):
        """parses a project page to get a representative image for that project"""

        # getting our previously declared item by using metadata, per:
        # https://media.readthedocs.org/pdf/scrapy/1.0/scrapy.pdf, section 3.9 requests and responses
        item = response.meta["item"]
        # https://tech.shareaholic.com/2012/11/02/how-to-find-the-image-that-best-respresents-a-web-page/
        # look for og:image as the image that best represents the project
        image = response.xpath('//meta[@property="og:image"]')
        item["image_url"] = image.xpath('@content').extract_first()
        yield item

class SearchSpider(Spider):
    # name of the spider, used to launch the spider
    name = "Search"

    # http://stackoverflow.com/questions/9681114/how-to-give-url-to-scrapy-for-crawling
    def __init__(self, *args, **kwargs):
        super(SearchSpider, self).__init__(*args, **kwargs)
        # http://stackoverflow.com/questions/15611605/how-to-pass-a-user-defined-argument-in-scrapy-spider
        # passing in our category argument
        self.category = kwargs.get("category")
        self.start_urls = ["http://www.makezine.com/page/1/?s=%s" % kwargs.get("category")]

    # starting the chain of requests, as with ProjectSpider
    def parse(self, response):
        # list of html elements with xpath that leads to project link
        projects = response.xpath('//div[contains(@class, "media-body")]/h2/a')

        # ensure this list is not empty (site format is same)
        if projects.extract_first() is not None:
            for i in range(NUM_MAKEZINE_PROJECTS):
                # declare instance of a DiynowItem and start to fill in fields
                item = DiynowItem()
                process_info(projects, item)
                # find the url for the page of the random project of "item"
                project_page = response.urljoin(item["url"])

                # parse that random project page, and update item's image_url field
                request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
                request.meta["item"] = item

                yield request
            # http://stackoverflow.com/questions/17560575/using-scrapy-to-extract-information-from-different-sites
            # passing request to next site, instructables
            url = "http://www.instructables.com/howto/%s" % self.category
            yield Request( url=url, callback=self.parse_instructables_projects, dont_filter = True)

    def parse_instructables_projects(self, response):
        # list of html elements with xpath that leads to project link
        projects = response.xpath('//div[contains(@class, "cover-item")]/a')

        if projects.extract_first() is not None:
            for i in range(NUM_INSTRUCTABLES_PROJECTS):
                # declare instance of a DiynowItem and start to fill in fields
                item = DiynowItem()
                process_instructables_info(projects, item)
                # find the url for the page of the random project of "item"
                project_page = response.urljoin(item["url"])
                # the instructables search page requires a modified url
                item["url"] = project_page

                # parse that random project page, and update item's image_url field
                request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
                request.meta["item"] = item

                yield request
        # http://stackoverflow.com/questions/17560575/using-scrapy-to-extract-information-from-different-sites
        # passing request to next site, lifehacker
        url = "https://lifehacker.com/search?q=%s" % self.category
        yield Request( url=url, callback=self.parse_lifehacker_projects, dont_filter = True)

    def parse_lifehacker_projects(self, response):
        # list of html elements with xpath that leads to project link
        projects = response.xpath('//h1[contains(@class, "headline entry-title js_entry-title")]/a')

        if projects.extract_first() is not None:
            for i in range(NUM_LIFEHACKER_PROJECTS):
                # declare instance of a DiynowItem and start to fill in fields
                item = DiynowItem()
                process_info(projects, item)

                # find the url for the page of the random project of "item"
                project_page = response.urljoin(item["url"])

                # parse that random project page, and update item's image_url field
                request = Request(project_page, callback = self.parse_project_page, dont_filter = True)
                request.meta["item"] = item

                yield request

    def parse_project_page(self, response):
        # getting our previously declared item by using metadata, per:
        # https://media.readthedocs.org/pdf/scrapy/1.0/scrapy.pdf, section 3.9 requests and responses
        item = response.meta["item"]
        # https://tech.shareaholic.com/2012/11/02/how-to-find-the-image-that-best-respresents-a-web-page/
        # look for og:image as the image that best represents the project
        image = response.xpath('//meta[@property="og:image"]')
        item["image_url"] = image.xpath('@content').extract_first()
        yield item

def process_info(projects, item):
    """when given a project xpath, extracts the title and url """
    # chose a random number between 0 and the number of projects in projects
    rand_num = random.randrange(0, len(projects))

    # get the title and url info out of that random number project
    # this process could fail if the section formatted oddly, if so, get a different project
    try:
        item["title"] = (projects.xpath('text()').extract())[rand_num]
        item["url"] = (projects.xpath('@href').extract())[rand_num]
    except IndexError:
        process_info(projects, item)

def process_instructables_info(projects, item):
    """unfortunately instructables search page uses different xpath, this modified
       function is for dealing with that modification"""
    # chose a random number between 0 and the number of projects in projects
    rand_num = random.randrange(0, len(projects))

    # get the title and url info out of that random number project
    # this process could fail if the section is formatted oddly, if so, get a different project
    try:
        item["title"] = (projects.xpath('@title').extract())[rand_num]
        item["url"] = (projects.xpath('@href').extract())[rand_num]
    except IndexError:
        process_info(projects, item)

