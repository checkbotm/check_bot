def get_yandex_map_link(points):
    # Проверяем, достаточно ли точек для формирования маршрута
    if len(points) < 2:
        raise ValueError("Должно быть как минимум две точки для формирования маршрута.")

    # Формируем начальную и конечную точки
    destination = points[-1]

    # Формируем промежуточные точки, если они есть
    waypoints = "~".join(points[:-1]) if len(points) > 1 else ""

    # Составляем полный URL для маршрута
    link = f"https://yandex.uz/maps/?rtext=~{waypoints}~{destination}&rtt=auto"

    return link

