#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec4 color;

varying vec2 texCoord;

void main()
{
    // Шейдер заливает текстуру (sampler2D textureRgba) переданным цветом (vec4 color), сохраняя ее альфу
	vec4 texColor = texture2D(textureRgba, texCoord);
	gl_FragColor = vec4(color.r, color.g, color.b, texColor.a);
}