#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec3 object_index;
uniform float threshold;

varying vec4 vertexColor;
varying vec2 texCoord;

void main()
{
    float alpha = step(threshold, texture2D(texture, texCoord).a * vertexColor.a);
    gl_FragColor = vec4(object_index.rgb, alpha);
}
