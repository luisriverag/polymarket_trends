DONE
db is not changing size, is it really getting and storing new data from API?
add indexes to db with the views for cards so it loads faster
is refresh refreshing data neccesary for all cards? eg resolved yes & no counter hasnt changed, active markets always displays 10000...
is it adding new data to the db continously and updating what it displays? add unit tests to confirm
in top markets by volume display both 24h trading volume and total trading volume for each event
how is market sentiment average yes price calculated? 21% seems wrong, so does bearish vs bullish scores
how is probability distribution calculated? does it take into account the number of potential outcomes per event? perhap>
option to select timezone (New York, London, Madrid, Dubai, Tokyo)




DOING



TO DO
displaying too many decimals in volume weighted sentiment calculation
load all markets with over $1000 in bets, dont hard cap to 10000 markets
improve how data from polymarket is queried and stored, db architecture doesnt seem efficient
add unit tests
