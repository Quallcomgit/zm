#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec4 color;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
	vec4 texColor = texture2D(texture, texCoord);
	float desaturated = dot(texColor, vec4(0.2126, 0.7152, 0.0722, 0.0));
	gl_FragColor = color * vec4(desaturated, desaturated, desaturated, texColor.a) * vertexColor;
}