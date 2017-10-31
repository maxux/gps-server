// prevent roboto to be loaded
// https://stackoverflow.com/a/25902239/1974533
var head = document.getElementsByTagName('head')[0];
var insertBefore = head.insertBefore;

head.insertBefore = function(newElement, referenceElement) {
    if(newElement.href && newElement.href.indexOf('//fonts.googleapis.com/css?family=Roboto') > -1)
        return;

    insertBefore.call(head, newElement, referenceElement);
};

function triptime(data) {
    var departure = data[0]['timestamp'];
    var arrival = data[data.length - 1]['timestamp'];

    return arrival - departure;
}

//
// gps data
//
function compute(data) {
    var output = {};
    var fullpath = [];

    output['segments'] = [];
    output['points']   = [];
    output['speeds']   = [];
    output['elevate']  = [];
    output['satsview'] = [];
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
        // avoid missing position
        if(!data[idx]['coord']['lat'] || !data[idx]['coord']['lng'])
            continue;

        // avoid missing position (for second point of the segment)
        if(!data[idx + 1]['coord']['lat'] || !data[idx + 1]['coord']['lng'])
            continue;

        // insert values to full trip
        fullpath.push(data[idx]['coord']);
        fullpath.push(data[idx + 1]['coord']);

        // create a new segment
        output['segments'].push([data[idx]['coord'], data[idx + 1]['coord']]);

        // computing relative data
        var time = data[idx]['datetime'].substr(11, 8);
        output['speeds'].push([time, parseInt(data[idx]['speed'])]);
        output['points'].push([time, data[idx]['coord']]);
        output['elevate'].push([time, parseInt(data[idx]['altitude'])]);
        output['satsview'].push([time, data[idx]['sats']]);

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
