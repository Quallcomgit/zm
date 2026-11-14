#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec4 color;

varying vec2 texCoord;

void main()
{
	vec4 texColor = texture2D(textureRgba, texCoord);
	float desaturated = dot(texColor.rgb, vec3(0.2126, 0.7152, 0.0722));
	gl_FragColor = color * vec4(desaturated, desaturated, desaturated, texColor.a);
}