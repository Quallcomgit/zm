#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec4 color;

varying vec2 texCoord;

void main()
{
	vec4 outColor = texture2D(textureRgba, texCoord) * color;
	gl_FragColor = vec4(outColor.rgb, outColor.a > 0.6 ? 1.0 : 0.0);
}
