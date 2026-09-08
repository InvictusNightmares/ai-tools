float op = opacity*clamp(1.-abs(vWorldPosition.x)/14.,0.,1.);
        vec4 diffuseColor = vec4( diffuse, op );
