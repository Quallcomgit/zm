#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;

uniform vec4 glowColor;
uniform vec2 dimension;
uniform float radius;

varying vec4 vertexColor;
varying vec2 texCoord;

vec4 texSample(sampler2D sampler, vec2 pos)
{
    vec4 color = texture2D(sampler, pos);
    return vec4(color.rgb, step(0.5, color.a));
}

void main()
{
    vec4 tempColor = texture2D(texture, texCoord);

    // Render outline. Otherwise: render an object itself
    if(tempColor.a < 0.5)
    {
        vec2 dxdyPls = (radius / dimension) * 0.5;

        vec2 xCs = vec2(dxdyPls.x, 0.0);
        vec2 yCs = vec2(0.0, dxdyPls.y);

        dxdyPls *= 0.7071; // aprox. 1 / sqrt(2) for diagonal offset
        vec2 dxdyMns = vec2(dxdyPls.x, -dxdyPls.y);

        // sample by 8 points
        vec4 c = texSample(texture, texCoord + dxdyPls) +
             texSample(texture, texCoord - dxdyPls) +
             texSample(texture, texCoord + dxdyMns) +
             texSample(texture, texCoord - dxdyMns) +
             texSample(texture, texCoord + xCs) +
             texSample(texture, texCoord - xCs) +
             texSample(texture, texCoord + yCs) +
             texSample(texture, texCoord - yCs);

         tempColor = glowColor;
         tempColor.a *= c.a;
    }

	gl_FragColor = tempColor * vertexColor;
}