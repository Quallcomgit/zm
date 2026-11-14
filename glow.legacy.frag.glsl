#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;

uniform vec4 color;
uniform vec2 dimension;
uniform float radius;

varying vec2 texCoord;

void main()
{
    // Sample current point
    vec4 tempColor = texture2D(textureRgba, texCoord);

    // Render outline. Otherwise: render an object itself
    if(tempColor.a < 0.5)
    {
        vec2 dxdyPls = (radius / dimension) * 0.5;

        vec2 xCs = vec2(dxdyPls.x, 0.0);
        vec2 yCs = vec2(0.0, dxdyPls.y);

        dxdyPls *= 0.7071; // aprox. 1 / sqrt(2) for diagonal offset
        vec2 dxdyMns = vec2(dxdyPls.x, -dxdyPls.y);
        
        // sample by 8 points
        vec4 c = texture2D(textureRgba, texCoord + dxdyPls) + 
             texture2D(textureRgba, texCoord - dxdyPls) +
             texture2D(textureRgba, texCoord + dxdyMns) + 
             texture2D(textureRgba, texCoord - dxdyMns) +
             texture2D(textureRgba, texCoord + xCs) + 
             texture2D(textureRgba, texCoord - xCs) +
             texture2D(textureRgba, texCoord + yCs) + 
             texture2D(textureRgba, texCoord - yCs);

         tempColor = color;
         tempColor.a *= c.a;
    }

    gl_FragColor = tempColor;
}