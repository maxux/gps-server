function triptime(data) {
    var departure = data[0]['timestamp'];
    var arrival = data[data.length - 1]['timestamp'];

    return arrival - departure;
}

function compute(data) {
    var output = {};
    var fullpath = [];
    output['segments'] = [];
    output['speeds']   = [];
    output['speedavg'] = 0;
    output['speedmax'] = 0;

    output['departure'] = new Date(data[0]['timestamp'] * 1000);
    output['arrival'] = new Date(data[data.length - 1]['timestamp'] * 1000);

    // ensure we have pair value
    if(data.length % 2)
        data.pop();

    // compute trip time
    output['totaltime'] = triptime(data);

    // parsing trip
    for(var idx = 0; idx < data.length; idx += 2) {
        // insert values to full trip
        fullpath.push(data[idx]['coord']);
        fullpath.push(data[idx + 1]['coord']);

        // create a new segment
        output['segments'].push([data[idx]['coord'], data[idx + 1]['coord']]);

        // computing speed
        output['speeds'].push(data[idx]['speed']);
        output['speedavg'] += data[idx]['speed'];

        if(data[idx]['speed'] > output['speedmax'])
            output['speedmax'] = data[idx]['speed'];
    }

    var fullpolypath = new google.maps.Polyline({path: fullpath, geodesic: true});
    output['length'] = google.maps.geometry.spherical.computeLength(fullpolypath.getPath().getArray());
    output['speedavg'] = output['speedavg'] / output['speeds'].length;

    // console.log(output);

    return output;
}

function live(data) {
    var output = {};

    output = data;
    output['update'] = new Date(data['timestamp'] * 1000);
    output['status'] = 'online';

    if(data['timestamp'] + 60 < (Date.now() / 1000))
        output['status'] = 'offline';

    return output;
}
