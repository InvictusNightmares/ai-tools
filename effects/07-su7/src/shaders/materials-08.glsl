#include <fog_vertex>
            vec3 worldNormal = normalize( vec3( vec4( normal, 0.0 ) * modelMatrix ) );
            vec3 cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
            reflectVec = reflect( cameraToVertex, worldNormal);
            vPosW = worldPosition.xyz;
