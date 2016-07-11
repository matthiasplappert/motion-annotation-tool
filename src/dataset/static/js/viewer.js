var scene, camera, renderer, controls, ambientLight, lights, data;
var update_slider= true;
var markers, lines, marker_line_mapping;
var marker_connections = {
	'kit': {
		// Head
		'LFHD': ['RFHD', 'LBHD'],
		'RBHD': ['RFHD', 'LBHD'],

		// Torso
		'C7': ['RFHD', 'LBHD', 'RBHD', 'LFHD', 'CLAV', 'LSHO', 'RSHO'],
		'STRN': ['CLAV', 'RASI', 'LASI'],
		'T10': ['LSHO', 'RSHO'],
		'L3': ['LPSI', 'RPSI', 'T10'],

		// Left arm and hand
		'LUPA': ['LSHO', 'LAEL'],
		'LAEL': ['LFRA'],
		'LFRA': ['LWTS'],
		'LWPS': ['LHPS', 'LWTS'],
		'LHTS': ['LWTS', 'LIFD'],
		'LHPS': ['LIFD'],

		// Right arm and hand
		'RUPA': ['RSHO', 'RAEL'],
		'RAEL': ['RFRA'],
		'RFRA': ['RWTS'],
		'RWPS': ['RHPS', 'RWTS'],
		'RHTS': ['RWTS', 'RIFD'],
		'RHPS': ['RIFD'],

		// Left leg
		'LHIP': ['LASI', 'LPSI'],
		'LTHI': ['LHIP'],
		'LKNE': ['LTHI', 'LTIP'],
		'LHEE': ['LTIP', 'LANK', 'LMT1'],
		'LMT5': ['LANK', 'LTOE'],
		'LMT1': ['LTOE'],

		// Right leg
		'RHIP': ['RASI', 'RPSI'],
		'RTHI': ['RHIP'],
		'RKNE': ['RTHI', 'RTIP'],
		'RHEE': ['RTIP', 'RANK', 'RMT1'],
		'RMT5': ['RANK', 'RTOE'],
		'RMT1': ['RTOE']
	},
	'cmu': {
		// Head
		'LFHD': ['RFHD', 'LBHD'],
		'RBHD': ['RFHD', 'LBHD'],

		// Torso
		'C7': ['RFHD', 'LBHD', 'RBHD', 'LFHD', 'CLAV', 'LSHO', 'RSHO'],
		'STRN': ['CLAV', 'RFWT', 'LFWT'],
		'T10': ['LSHO', 'RSHO', 'LBWT', 'RBWT'],
		'LBWT': ['RBWT'],

		// Left arm and hand
		'LUPA': ['LSHO', 'LELB'],
		'LELB': ['LFRM'],
		'LFRM': ['LWRA', 'LWRB'],
		'LFIN': ['LWRA', 'LWRB'],

		// Right arm and hand
		'RUPA': ['RSHO', 'RELB'],
		'RELB': ['RFRM'],
		'RFRM': ['RWRA', 'RWRB'],
		'RFIN': ['RWRA', 'RWRB'],

		// Left leg
		'LTHI': ['LFWT', 'LBWT'],
		'LKNE': ['LTHI', 'LSHN'],
		'LHEE': ['LSHN', 'LANK'],
		'LMT5': ['LANK', 'LTOE'],
		'LANK': ['LTOE'],

		// Right leg
		'RTHI': ['RFWT', 'RBWT'],
		'RKNE': ['RTHI', 'RSHN'],
		'RHEE': ['RSHN', 'RANK'],
		'RMT5': ['RANK', 'RTOE'],
		'RANK': ['RTOE']
	}
};

var frame_idx = 0, prev_frame_idx = -1;
var playing = true;
var looping = false;

// Taken from http://stackoverflow.com/questions/9899807/three-js-detect-webgl-support-and-fallback-to-regular-canvas
function webglAvailable() {
	try {
		var canvas = document.createElement("canvas");
		return !!
		window.WebGLRenderingContext && 
		(canvas.getContext("webgl") || 
			canvas.getContext("experimental-webgl"));
	} catch(e) { 
		return false;
	} 
}

function initViewer(json_url, repeat, camera_position, target_position) {
	repeat = repeat || false;
	camera_position = camera_position || new THREE.Vector3(15., 15., 15.);
	target_position = target_position || new THREE.Vector3(0., 0., 10.);

	$.getJSON(json_url, function(d) {
		$('#motion-loading').hide();

		// Check if WebGL is available.
		if (!webglAvailable()) {
			var element = document.createElement('div');
			element.id = 'webgl-error-message';
			element.innerHTML = window.WebGLRenderingContext ? [
				'Your graphics card does not seem to support WebGL.',
				'Find out how to get it <a href="http://get.webgl.org/">here</a>.'
			].join( '\n' ) : [
				'Your browser does not seem to support WebGL.',
				'Find out how to get it <a href="http://get.webgl.org/">here</a>.'
			].join( '\n' );
			$('#motion').append(element);
			return;
		}
		$('#motion-container').show();
		
		data = d;
		looping = repeat;
		initUi();
		initScene(camera_position, target_position);
		initLights();
		initFloor();
		initMarkers();
		updateMarkers();
		render();
	});
};

function initUi() {
	window.setInterval(updateFrameIndexIfNecessary, data.interval);

	// Configure slider
	$('#motion-ui-slider').attr({
		'max' : data.frames.length - 1,
		'min' : 0
	});
	$('#motion-ui-slider').bind('mousedown', function() {
		update_slider = false;
		$('#motion-ui-slider').bind('mousemove', function() {
			playing = false;
			frame_idx = parseInt($('#motion-ui-slider').val());
			updateButton();
		});
	});
	$('#motion-ui-slider').bind('mouseup',function() {
		$('#motion-ui-slider').val(frame_idx);
		update_slider = true;
		$('#motion-ui-slider').unbind('mousemove');
	});

	// Configure play/pause button
	updateButton();
	$('#motion-ui-button').click(function() {
		playing = !playing;
		if (playing && frame_idx == data.frames.length - 1) {
			frame_idx = 0;
		}
		updateButton();
	});
};

function updateButton() {
	if (playing) {
		$('#motion-ui-button').val('Pause');
	} else {
		$('#motion-ui-button').val('Play');
	}
}

function initScene(camera_position, target_position) {
	targetElement = document.getElementById("motion-content");

	scene = new THREE.Scene();
	camera = new THREE.PerspectiveCamera(75, targetElement.offsetWidth / targetElement.offsetHeight, 0.001, 1000);
	camera.up.set( 0, 0, 1 );
	camera.position.x = camera_position.x;
	camera.position.y = camera_position.y;
	camera.position.z = camera_position.z;
	
	var options = { antialias: true, alpha: true };
	renderer = new THREE.WebGLRenderer(options);
	renderer.setPixelRatio(window.devicePixelRatio);
	renderer.setSize(targetElement.offsetWidth, targetElement.offsetHeight);
	renderer.setClearColor(0x000000, 0);
	targetElement.appendChild(renderer.domElement);

	controls = new THREE.OrbitControls(camera, renderer.domElement);
	controls.enableZoom = true;
	controls.enablePan = false;
	controls.target = target_position;
	controls.keys = [];
	controls.update();

	window.addEventListener('resize', function() {
		camera.aspect = targetElement.offsetWidth / targetElement.offsetHeight;
		camera.updateProjectionMatrix();
		renderer.setSize(targetElement.offsetWidth, targetElement.offsetHeight);
	}, false);
};

function updateTargetPositionIfAppropriate() {
	var direction = controls.object.position.sub(controls.target);
	var targetPosition = positionOfMarker('STRN');
	var cameraPosition = new THREE.Vector3().copy(targetPosition).add(direction);
	controls.target = targetPosition;
	controls.object.position.copy( cameraPosition );
	controls.update();
}

function vectorToString(vec) {
	return '(' + vec.x + ',' + vec.y + ',' + vec.z + ')';
};

function assert(condition, message) {
	if (!condition) {
		throw message || 'Assertion failed';
	}
};

function initLights() {
	ambientLight = new THREE.AmbientLight( 0xffffff );
	scene.add(ambientLight);
};

function initFloor() {
	// Based on https://gist.github.com/bhollis/7686441
	var segments = 16;
	var geometry = new THREE.PlaneGeometry(200, 200, segments, segments);
	var materialEven = new THREE.MeshBasicMaterial({color: 0x696969});
	var materialOdd = new THREE.MeshBasicMaterial({color: 0x9f9f9f});
	var materials = [materialEven, materialOdd];
	for (var x = 0; x < segments; x++) {
		for (var y = 0; y < segments; y++) {
			i = x * segments + y;
			j = 2 * i;
			geometry.faces[j].materialIndex = geometry.faces[j + 1].materialIndex = (x + y) % 2;
		}
	}
	floor = new THREE.Mesh(geometry, new THREE.MeshFaceMaterial(materials));
	scene.add(floor)
};

function markerIndexFromName(name) {
	for (var i in data.markers) {
		if (data.markers[i] == name) {
			return i;
		}
	}
	return -1;
};

function positionOfMarker(name) {
	for (var i in data.markers) {
		if (data.markers[i] == name) {
			var pos = data.frames[frame_idx][i];
			return new THREE.Vector3(data.frames[frame_idx][3 * i], data.frames[frame_idx][3 * i + 1], data.frames[frame_idx][3 * i + 2]);
		}
	}
	return -1;
}

function initMarkers() {
	var n_markers = data.markers.length;
	var marker_set = data.marker_set;
	if (!marker_set) {
		marker_set = 'kit';
	}
	markers = []
	for (var i = 0; i < n_markers; i++) {
		var geometry = new THREE.SphereGeometry(0.1, 32, 32 );
		var material = new THREE.MeshBasicMaterial( { color: 0x00ff00 } );
		var marker = new THREE.Mesh(geometry, material);
		markers.push(marker);
		scene.add(marker);
	}

	lines = []
	marker_line_mapping = []
	for (var start_marker_name in marker_connections[marker_set]) {
		for (var end_marker_idx in marker_connections[marker_set][start_marker_name]) {
			end_marker_name = marker_connections[marker_set][start_marker_name][end_marker_idx];
			start_idx = markerIndexFromName(start_marker_name);
			end_idx = markerIndexFromName(end_marker_name);
			if (start_idx < 0 || end_idx < 0) {
				// Some motions do not have all markers. Not to worry, simply skip this connection.
				continue;
			}
			
			// Create line.
			var material = new THREE.LineBasicMaterial({
				color: 0x0000ff,
				linewidth: 2.0
			});
			var geometry = new THREE.Geometry();
			geometry.vertices.push(
				new THREE.Vector3(0, 0, 0),
				new THREE.Vector3(0, 0, 0)
				);
			var line = new THREE.Line(geometry, material);
			line.frustumCulled = false;
			line.dynamic = true;
			lines.push(line);
			marker_line_mapping.push([start_idx, end_idx])
			scene.add(line);
		}
	}
};

function updateMarkers() {
	for (var i = 0; i < markers.length; i++) {
		var marker = markers[i];
		marker.position.x = data.frames[frame_idx][i * 3 + 0];
		marker.position.y = data.frames[frame_idx][i * 3 + 1];
		marker.position.z = data.frames[frame_idx][i * 3 + 2];
	}

	for (var i in lines) {
		mapping = marker_line_mapping[i];
		start_marker = markers[mapping[0]]
		end_marker = markers[mapping[1]]
		line = lines[i];
		line.geometry.vertices = [start_marker.position, end_marker.position];
		line.geometry.verticesNeedUpdate = true;
	}
};

function render() {
	requestAnimationFrame(render);
	if (frame_idx != prev_frame_idx) {
		updateTargetPositionIfAppropriate();
		updateMarkers();
	}
	renderer.render(scene, camera);
	prev_frame_idx = frame_idx;
};

function updateFrameIndexIfNecessary() {
	if (playing && (looping || frame_idx < data.frames.length - 1)) {
		frame_idx = (frame_idx + 1) % data.frames.length;
	}
	if (!looping && frame_idx == data.frames.length - 1) {
		playing = false;
		updateButton();
	}
	if (update_slider) {
		$("#motion-ui-slider").val(frame_idx);
	}
};
