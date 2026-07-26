var express = require('express'),
    async = require('async'),
    redis = require('redis'), // <-- Remplacement de 'pg' par 'redis'
    cookieParser = require('cookie-parser'),
    app = express(),
    server = require('http').Server(app),
    io = require('socket.io')(server),
    path = require('path');

var port = process.env.PORT || 4000;

io.on('connection', function (socket) {
  socket.emit('message', { text : 'Welcome!' });

  socket.on('subscribe', function (data) {
    socket.join(data.channel);
  });
});

// Connexion au conteneur Redis (via bridge-bk)
var client = redis.createClient({
  host: 'redis',
  port: 6379
});

client.on('error', function (err) {
  console.error("Waiting for redis / db proxy...");
});

client.on('connect', function () {
  console.log("Connected to Redis (Backend Bridge) successfully");
  getVotes();
});

function getVotes() {
  // On récupère directement l'état des votes stockés dans Redis
  client.hgetall('voted_counts', function (err, reply) {
    if (err) {
      console.error("Error performing Redis query: " + err);
    } else {
      var votes = {
        a: reply && reply.a ? parseInt(reply.a) : 0,
        b: reply && reply.b ? parseInt(reply.b) : 0
      };
      io.sockets.emit("scores", JSON.stringify(votes));
    }

    // On rafraîchit toutes les secondes
    setTimeout(getVotes, 1000);
  });
}

app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(__dirname + '/views'));

app.get('/', function (req, res) {
  res.sendFile(path.resolve(__dirname + '/views/index.html'));
});

server.listen(port, function () {
  console.log('App running on port ' + port);
});