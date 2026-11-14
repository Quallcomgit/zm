#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
    float a = texture2D(texture, texCoord.xy).a;
    gl_FragColor = vec4(vertexColor.rgb, vertexColor.a * a);
}
