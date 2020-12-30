# Mediamail Design

## Overview
Media mail works as a trio of bots representing an interaction with a social media platform
* Platform Bot: These reach out to a specific social media application, e.g. Twitter and funnel data into a common Elastic Search index
* Mail Bot: These query the common Elastic Search index on behalf of a user, given user preferences
* Reply Bot: These manage replies from a user, given user preferences, and then interact back with the social media Platform accordingly

## Configuration
All configuration of bots is found in the `run` folder which are then executed at run time. The `conf` folder is reserved for example templates meant to be copied and filled in and placed in `run`. An example might be copying `twitterbot.json` into `run\twitterbot_mytracks.json` to fill in a specific Twitter bot configuration.

### Configuring Global Properties
The `global.json` file is where properties for all bot types can be found:

`elastic`: This contains the host, port and index name to use.

`user_identification`: This contains information such as the social media handle names that represent the user.

### Configuring Twitter Bot
The `twitterbot.json

`filters`: These are lists of `string` that set up various filters. `blacklist_words` will exclude any Tweet from going into Elastic Search that contains any of these words. Useful for pornographic or other offensive material filtering. `whitelist_words` will only accept Tweets to put into Elastic Search if they contain the word. `blacklist_words` is checked first ahead of `whitelist`. `common_words` is used in tokenizing a Tweet so that these words are not considered tokens for searching upon, e.g. there would be zillions of hits on the word "the"

`locality`: These help Twitter Bot figure out of a tweet is from an author near to you. The `local_towns` list of `string` should be filled in with local town names, e.g. `Berlin` or `Voorhees` without specifying the state. `state` and `state_abbreivation` are the United State states and its postal abbreviation, e.g. `New Jersey` and `NJ`

`queries`: This is where you set what kind of streaming query to Twitter you'd like to set up. 
* `aois`: This is a list of `float` that defines geographical boxes in latitude and longitudes where each box is a quadruplet: `sw_lon`, `sw_lat`, `nw_lon`, `nw_lat`. The list can be any length of quadruplets and the length of the list modulo four should be zero.
* `followers`: This is a list of `integer` that represent Twitter user IDs. When setting this up the Twitter Bot will track for updates from these users. Helpful for things like your followers list or people you might follow.
* `tracks`: This is a list of `string` representing key words you want to set up a query for. For example, `pray` would start scanning Twitter for all tweets that contain that word.

`twitter`: This is access information needed to set up a Twitter connection and it also contains the user handle name used. To understand this more, please see: https://developer.twitter.com/en

## Mailbot Design

globalReply: Mailbot contains a dictionary `{}` containing lists `[]` of reponses where the key in the dictionary is the `title` given to the query found in the `queries` section of `mailbot.json`.  The list is populated with hits found in the Elastic Search database that match the query criteria. A `hit_limit` is respected. Once the limit is reached, only the highest scoring items in the list are kept. Each hit in the list of a reply is also a dictionary containing:

* `score`: the score of the hit
* `id`: the unique identification of the hit 
* `text`: the fullly prepared message
* `link`: direct URL to the actual message

## Scoring
Each message sent to the user via an email has an `integer` score associated with it. This is determined by several factors which are configured in Mailbot's mailbot.json (see above). 

Scoring is determined as follows:
* Disinterested Words: A dictionary of `string:integer` where each string is a key word of disinterest to the user being sent the mail. This does not act as a filter, rather as a means to score messages. The `integer` specified is how many points are subtracted for that word. Recommended that each `integer` be at least -25 as keyword matches are not important to bury less important messages.
* Hashtag Heck: Many times a message may come in with many hashtags (e.g. the `#` symbol) in it which are just very short messages that are designed to grab a lot of attention. This is an `integer` that will be decremented of the overall score per hashtag used. Recommended value is -25.
* Interested Words: A dictionary of `string:integer` where each string is a key word of interest to the user being sent the mail. This does not act as a filter, rather as a means to score messages. The `integer` specified is how many points given to that word. Recommended that each `integer` be at least 25 as keyword matches are important for surfacing up important messages.
* Locality: Messages that come from an author near a configured location are considered local to that location. Locality confidence is determined by matching the author's provided location information to that of the configuration. Locality confidence is a value 0.0 to 1.0 where 0.0 is certainly not local and 1.0 is certainly local. The product of `locality_multiplier` with the locality confidence awards a certain number of points for each message. Recommended value is `250`. A few examples with the recommended value would be: a locality confidence of 1.0 would award 250 points, a confidence of 0.5 would award 125 points, and a confidence of 0.1 would award 25 points.
* Number of points per word in the message: Short messages are less intereting. It was once said the average length of a tweet is 6 characters. The number of points per word is configured in the `points_per_word` setting. Recommended value is `1`.
* Shoutout Heck:  Many times a message may come in with many shoutouts (e.g. the `@` symbol) in it which are just very short messages that are designed to grab a lot of attention. This is an `integer` that will be decremented of the overall score per shoutout used. Recommended value is -50.
* Shoutout to Me: If a message is directed to the user, additional scoring can happen. This is checked by comparing the references in the message compared to what is configured in the `user_identification` global.json setting under the sub-property `social_media_handles`. Recommended value is 500, to elevate these above the others.

