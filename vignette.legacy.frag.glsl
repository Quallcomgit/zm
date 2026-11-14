#ifdef GL_ES
precision highp float;
#endif

uniform vec4 color;
uniform vec2 center;
uniform vec2 size;
uniform float radius;
uniform float softness;
uniform float alpha;

void main()
{
	// Нормализуем пточку по Y. Достаточно отскейлить по одной координате.
    // Центру делаем флип по Y. Из-за того, что у нас флипнутая система координат.
    // Можно было бы подумать над тем, чтобы делать это преобразование при установке
    // uniform в коде игры.
    vec2 position = (gl_FragCoord.xy - vec2(center.x, size.y - center.y)) / size.yy;

    // Наша основная метрика, это расстояние от центра
    float len = length(position);

    // Т.к. нормализация position была по y, радиус скейлим тоже на y
    float r = radius / size.y;
    // Делаем плавный переход от 0 к 1
    float value = smoothstep(r, r - softness, len);
    // Альфу надо флипнуть. Домножаем на красноватый оттенок, чтобы получить мягкий свет по краю. 
    gl_FragColor = vec4(vec3(value), (1.0 - value)) * vec4(0.7, 0.3, 0.2, alpha);
}
