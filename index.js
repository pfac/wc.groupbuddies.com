var express = require('express');
var pg = require('pg');
var app = express();

app.set('views', __dirname);
app.set('view engine', 'jade');
app.set('port', (process.env.PORT || 5000));
app.use(express.static(__dirname));

handlePGError = function(err) {
  if (err) return console.error('could not connect to postgres', err);
}

connections = []

app.get('/updates', function(req, res) {
  req.socket.setTimeout(Infinity);

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  });
  res.write('\n');

  connections.push(res);
  req.on('close', function() {
    var index = connections.indexOf(res);
    if (index !== -1) connections.splice(index, 1);
  });
});

app.get('/', function(req, res) {
  pg.connect(process.env.DATABASE_URL, function(err, client, done) {
    handlePGError(err);

    var query = 'SELECT * FROM bathrooms'
    client.query(query, function(err, result) {
      done();
      if (err) {
        console.error(err);
        res.send("Error " + err);
      } else {
        var status = result.rows[0].status;
        res.render('index', {
          title:     status ? "Someone's in there" : "Go ahead!",
          css_class: status ? "busy" : "free"
        });
      }
    });
  });
});

app.put('/api/:name/:value', function(req, res) {
  var state = (req.params.value === "true")

  pg.connect(process.env.DATABASE_URL, function(err, client, done) {
    handlePGError(err);

    var query = 'UPDATE bathrooms SET status=($1), updated_at=($2) WHERE name=($3)';
    client.query(query, [state, new Date(), req.params.name], function(err, result) {
      done();
      if (err) {
        console.error(err);
        res.sendStatus(500);
      } else {
        var status = state ? "busy" : "free"
        connections.forEach(function(conn) {
          conn.write('data: ' + status + '\n\n');
        });

        res.sendStatus(200);
      }
    });
  });
});

app.listen(app.get('port'), function() {
  console.log("Node app is running at localhost:" + app.get('port'))
});
